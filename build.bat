@echo off
setlocal
title Build YT-DL PLAI
echo.
echo ══════════════════════════════════════════
echo   Build YT-DL PLAI
echo ══════════════════════════════════════════
echo.

REM ── 1. Vérifie Python ──────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python introuvable dans le PATH.
    echo Installer depuis https://www.python.org/downloads/
    pause & exit /b 1
)

REM ── 2. Vérifie ffmpeg.exe ──────────────────────────────────
if not exist "ffmpeg.exe" (
    echo ERREUR : ffmpeg.exe manquant dans ce dossier.
    echo.
    echo   1. Telecharger ffmpeg-release-essentials.zip depuis :
    echo      https://www.gyan.dev/ffmpeg/builds/
    echo   2. Extraire bin\ffmpeg.exe dans ce dossier.
    echo   3. Relancer build.bat.
    echo.
    pause & exit /b 1
)

REM ── 3. Installe les dépendances Python ────────────────────
echo [1/3] Installation des dependances...
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

REM ── 4. PyInstaller ────────────────────────────────────────
echo [2/3] Compilation PyInstaller...
pyinstaller ^
    --noconfirm ^
    --onedir ^
    --name "YT-DL PLAI" ^
    --add-data "templates;templates" ^
    --add-binary "ffmpeg.exe;." ^
    --hidden-import "yt_dlp" ^
    --hidden-import "yt_dlp.extractor" ^
    --hidden-import "yt_dlp.postprocessor" ^
    --hidden-import "flask" ^
    --hidden-import "engineio" ^
    app.py

if errorlevel 1 (
    echo.
    echo ERREUR PyInstaller. Voir le log ci-dessus.
    pause & exit /b 1
)

REM ── 5. Inno Setup (optionnel) ─────────────────────────────
echo [3/3] Recherche Inno Setup...
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"

if exist %ISCC% (
    echo Inno Setup trouve — creation de l'installateur...
    %ISCC% installer.iss
    echo.
    echo ══════════════════════════════════════════
    echo   SUCCES : Output\YT-DL-PLAI-Setup.exe
    echo ══════════════════════════════════════════
) else (
    echo Inno Setup absent — le .exe brut est dans dist\YT-DL PLAI\
    echo Pour creer un installateur, installer Inno Setup :
    echo   https://jrsoftware.org/isdl.php
    echo puis relancer ce script.
)

echo.
pause
endlocal
