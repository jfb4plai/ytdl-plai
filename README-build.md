# YT-DL PLAI — Guide de build

## Prérequis (à faire une seule fois)

### 1. Python 3.11+
https://www.python.org/downloads/
Cocher "Add python.exe to PATH" pendant l'installation.

### 2. ffmpeg.exe
1. Télécharger `ffmpeg-release-essentials.zip` depuis https://www.gyan.dev/ffmpeg/builds/
2. Extraire le zip
3. Copier `bin/ffmpeg.exe` dans le dossier `ytdl-plai/` (à côté de `app.py`)

### 3. Inno Setup 6 (pour créer l'installateur .exe)
https://jrsoftware.org/isdl.php

---

## Construire l'installateur

```
Double-clic sur build.bat
```

Le script fait tout automatiquement :
1. Installe les dépendances Python (flask, yt-dlp, pyinstaller)
2. Compile `app.py` → `dist/YT-DL PLAI/YT-DL PLAI.exe` via PyInstaller
3. Lance Inno Setup → `Output/YT-DL-PLAI-Setup.exe`

**Fichier à distribuer aux enseignants : `Output/YT-DL-PLAI-Setup.exe`**

---

## Tester sans compiler

```bash
pip install -r requirements.txt
# Placer ffmpeg.exe dans le dossier
python app.py
```
Le navigateur s'ouvre automatiquement sur http://localhost:7890

---

## Mettre à jour yt-dlp (si YouTube change ses protections)

Les enseignants n'ont rien à faire — yt-dlp se met à jour automatiquement.

Pour l'inclure dans un nouveau build :
```bash
pip install -U yt-dlp
build.bat
```

---

## Structure du projet

```
ytdl-plai/
├── app.py              Backend Flask + yt-dlp
├── templates/
│   └── index.html      Interface utilisateur
├── requirements.txt
├── build.bat           Script de compilation
├── installer.iss       Script Inno Setup
├── ffmpeg.exe          À placer manuellement (non versionné)
├── dist/               Généré par PyInstaller
└── Output/             Contient YT-DL-PLAI-Setup.exe
```

---

## Notes légales

- Usage pédagogique privé, en classe, non redistribué
- Contenu téléchargé = accès hors ligne, pas de copie commerciale
- Les CGU YouTube interdisent techniquement le téléchargement — usage toléré en pratique pour usage privé
