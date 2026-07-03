"""
YT-DL PLAI — Backend Flask + yt-dlp
Téléchargeur YouTube local, usage pédagogique privé.
"""

import sys
import os
import re
import threading
import webbrowser
import json
import time
import socket
import urllib.request
import urllib.error

from flask import Flask, render_template, request, Response, jsonify
import yt_dlp

app = Flask(__name__, template_folder="templates")

# ── État global du téléchargement ────────────────────────────────────────────
_state = {
    "status": "idle",   # idle | starting | downloading | processing | done | error | cancelled
    "percent": 0.0,
    "speed": "",
    "eta": "",
    "title": "",
    "error": "",
}
_cancel_event = threading.Event()
_lock = threading.Lock()

PORT = 7890


# ── Utilitaires ───────────────────────────────────────────────────────────────

def reset_state(status="idle"):
    with _lock:
        _state.update({"status": status, "percent": 0.0,
                        "speed": "", "eta": "", "title": "", "error": ""})


def set_state(**kwargs):
    with _lock:
        _state.update(kwargs)


def get_downloads_folder():
    """Détecte le dossier Téléchargements (FR) ou Downloads (EN)."""
    for name in ("Téléchargements", "Downloads"):
        path = os.path.join(os.path.expanduser("~"), name)
        if os.path.isdir(path):
            return path
    # Fallback : crée Téléchargements
    path = os.path.join(os.path.expanduser("~"), "Téléchargements")
    os.makedirs(path, exist_ok=True)
    return path


def get_ffmpeg_path():
    """Localise ffmpeg.exe : bundle PyInstaller, dossier courant, ou PATH."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "ffmpeg.exe")
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
    return local if os.path.exists(local) else "ffmpeg"


def strip_ansi(text):
    """Supprime les codes couleur ANSI des messages d'erreur yt-dlp."""
    return re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", text)


def parse_vtt(vtt_text):
    """Extrait le texte lisible d'un fichier VTT YouTube (auto-généré ou manuel)."""
    lines = vtt_text.split("\n")
    text_lines = []
    prev = None
    for line in lines:
        line = line.strip()
        # Ignore header, timestamps, numéros de bloc, lignes de position
        if (not line
                or line.startswith("WEBVTT")
                or line.startswith("NOTE")
                or "-->" in line
                or re.match(r"^\d+$", line)
                or re.match(r"^(align|position|line|size):", line)):
            continue
        # Supprime toutes les balises HTML/cue (<c>, <00:00:00.000>, etc.)
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line != prev:
            text_lines.append(line)
            prev = line
    return "\n".join(text_lines)


def friendly_error(exc):
    """Transforme les erreurs techniques en messages lisibles."""
    msg = strip_ansi(str(exc))
    if "ffmpeg is not installed" in msg or ("ffmpeg" in msg.lower() and "not" in msg.lower()):
        return (
            "ffmpeg est requis pour le téléchargement en 1080p. "
            "Placer ffmpeg.exe dans le dossier de l'application."
        )
    if "429" in msg or "Too Many Requests" in msg:
        return (
            "YouTube limite les requêtes (erreur 429). "
            "Patientez 1-2 minutes et réessayez. "
            "Si l'erreur persiste, ouvrez YouTube dans Chrome et reconnectez-vous."
        )
    return msg[:300]


def get_cookie_opts():
    """Utilise les cookies Edge via yt-dlp natif."""
    return {"cookiesfrombrowser": ("edge",)}


# ── Hook de progression yt-dlp ────────────────────────────────────────────────

def progress_hook(d):
    if _cancel_event.is_set():
        raise yt_dlp.utils.DownloadCancelled()

    status = d.get("status")
    if status == "downloading":
        raw_pct = strip_ansi(d.get("_percent_str", "0%")).strip().replace("%", "")
        try:
            pct = float(raw_pct)
        except ValueError:
            pct = 0.0
        set_state(
            status="downloading",
            percent=round(pct, 1),
            speed=strip_ansi(d.get("_speed_str", "—")).strip(),
            eta=strip_ansi(d.get("_eta_str", "—")).strip(),
        )
    elif status == "finished":
        set_state(status="processing", percent=100.0, speed="", eta="")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def start_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "URL manquante"}), 400

    with _lock:
        if _state["status"] in ("starting", "downloading", "processing"):
            return jsonify({"error": "Téléchargement déjà en cours"}), 409

    _cancel_event.clear()
    reset_state("starting")

    def run():
        out_dir = get_downloads_folder()
        ydl_opts = {
            "format": (
                "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
                "/bestvideo[height<=1080]+bestaudio"
                "/best[height<=1080]"
                "/best"
            ),
            "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
            "ffmpeg_location": get_ffmpeg_path(),
            "merge_output_format": "mp4",
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "noprogress": False,
            **get_cookie_opts(),
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                set_state(title=info.get("title", url))
                if not _cancel_event.is_set():
                    ydl.download([url])
            if not _cancel_event.is_set():
                set_state(status="done", percent=100.0)
        except yt_dlp.utils.DownloadCancelled:
            set_state(status="cancelled")
        except Exception as exc:
            set_state(status="error", error=friendly_error(exc))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/progress")
def progress_stream():
    """Server-Sent Events : pousse l'état toutes les 250 ms."""
    def generate():
        last_json = None
        while True:
            with _lock:
                snap = dict(_state)
            j = json.dumps(snap, ensure_ascii=False)
            if j != last_json:
                yield f"data: {j}\n\n"
                last_json = j
                if snap["status"] in ("done", "error", "cancelled", "idle"):
                    break
            time.sleep(0.25)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/transcript", methods=["POST"])
def get_transcript():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL manquante"}), 400

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            # Priorité : sous-titres manuels FR, puis auto FR, puis EN
            "subtitleslangs": ["fr", "fr-BE", "fr-FR", "fr-CA", "en"],
            "subtitlesformat": "vtt",
            "outtmpl": os.path.join(tmp, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            **get_cookie_opts(),
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url)
                title = info.get("title", "")

            vtt_files = sorted(
                [f for f in os.listdir(tmp) if f.endswith(".vtt")],
                # Préfère les fichiers sans "auto" dans le nom (sous-titres manuels)
                key=lambda f: (1 if "auto" in f else 0)
            )
            if not vtt_files:
                return jsonify({"error": (
                    "Aucun sous-titre disponible pour cette vidéo. "
                    "Vérifier que la vidéo a des sous-titres activés."
                )}), 404

            chosen = vtt_files[0]
            lang = "fr" if ".fr" in chosen else ("en" if ".en" in chosen else "?")
            with open(os.path.join(tmp, chosen), encoding="utf-8") as f:
                raw = f.read()

            transcript = parse_vtt(raw)
            return jsonify({"ok": True, "title": title, "transcript": transcript, "lang": lang})

        except Exception as exc:
            return jsonify({"error": friendly_error(exc)}), 500


@app.route("/cancel", methods=["POST"])
def cancel():
    _cancel_event.set()
    return jsonify({"ok": True})


# ── Configuration (clé API) ───────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".ytdl-plai-config.json")

def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)

@app.route("/config", methods=["GET"])
def get_config():
    cfg = load_config()
    return jsonify({"has_key": bool(cfg.get("anthropic_key"))})

@app.route("/config", methods=["POST"])
def set_config():
    data = request.get_json(silent=True) or {}
    key = (data.get("anthropic_key") or "").strip()
    if not key:
        return jsonify({"error": "Clé manquante"}), 400
    cfg = load_config()
    cfg["anthropic_key"] = key
    save_config(cfg)
    return jsonify({"ok": True})


# ── Génération IA ─────────────────────────────────────────────────────────────

PROMPTS = {
    "questionnement": (
        "Tu es un assistant pédagogique. À partir du transcript ci-dessous, "
        "génère 7 questions de questionnement socratique couvrant les 6 niveaux "
        "de la taxonomie de Bloom révisée (mémorisation, compréhension, application, "
        "analyse, évaluation, création). "
        "Une question par niveau minimum. Format : niveau en gras, puis la question. "
        "Langue : celle du transcript. Pas d'introduction ni de conclusion."
    ),
    "quiz": (
        "Tu es un assistant pédagogique. À partir du transcript ci-dessous, "
        "génère 6 questions à choix multiple (QCM). "
        "Format pour chaque question : "
        "numéro et intitulé, puis A) B) C) D) sur des lignes séparées, "
        "puis 'Réponse : X' sur une nouvelle ligne. "
        "Langue : celle du transcript. Pas d'introduction ni de conclusion."
    ),
    "fiche": (
        "Tu es un assistant pédagogique. À partir du transcript ci-dessous, "
        "génère une fiche didactique structurée avec : "
        "1. Titre de la vidéo ; "
        "2. Résumé en 5 points essentiels (puces) ; "
        "3. Concepts clés (3 à 5 termes, chacun avec une définition courte) ; "
        "4. Question de réflexion pour la classe ; "
        "5. Prolongement suggéré (activité ou ressource). "
        "Langue : celle du transcript. Pas d'introduction ni de conclusion."
    ),
}

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    transcript = (data.get("transcript") or "").strip()
    mode = data.get("mode", "questionnement")

    if not transcript:
        return jsonify({"error": "Transcript manquant"}), 400
    if mode not in PROMPTS:
        return jsonify({"error": "Mode inconnu"}), 400

    cfg = load_config()
    api_key = cfg.get("anthropic_key", "")
    if not api_key:
        return jsonify({"error": "Clé API Anthropic non configurée. Cliquer sur ⚙️ pour l'ajouter."}), 401

    # Tronquer à 12 000 caractères pour éviter de dépasser les tokens Haiku
    transcript_trimmed = transcript[:12000]

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1200,
        "messages": [
            {
                "role": "user",
                "content": f"{PROMPTS[mode]}\n\n---\nTRANSCRIPT :\n{transcript_trimmed}\n---"
            }
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            text = result["content"][0]["text"]
            return jsonify({"ok": True, "result": text})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body[:300]
        if e.code == 401:
            msg = "Clé API invalide. Vérifier dans ⚙️."
        return jsonify({"error": msg}), 500
    except Exception as exc:
        return jsonify({"error": str(exc)[:200]}), 500


# ── Démarrage ─────────────────────────────────────────────────────────────────

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{PORT}")


@app.route("/quit", methods=["POST"])
def quit_app():
    """Arrête le serveur proprement depuis l'interface."""
    def shutdown():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=shutdown, daemon=True).start()
    return jsonify({"ok": True})


if __name__ == "__main__":
    if is_port_in_use(PORT):
        webbrowser.open(f"http://localhost:{PORT}")
    else:
        print("=" * 48)
        print("  YT-DL PLAI — serveur démarré")
        print(f"  Navigateur : http://localhost:{PORT}")
        print("  Fermer cette fenêtre pour arrêter l'app.")
        print("=" * 48)
        threading.Thread(target=open_browser, daemon=True).start()
        app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
