[Setup]
AppName=YT-DL PLAI
AppVersion=1.0
AppPublisher=PLAI - Pole Liegeois d'Accompagnement vers une Ecole Inclusive
DefaultDirName={autopf}\YT-DL PLAI
DefaultGroupName=YT-DL PLAI
OutputBaseFilename=YT-DL-PLAI-Setup
OutputDir=Output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Pas besoin de droits admin — installe dans AppData si besoin
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
Source: "dist\YT-DL PLAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\YT-DL PLAI";         Filename: "{app}\YT-DL PLAI.exe"
Name: "{group}\Desinstaller";       Filename: "{uninstallexe}"
Name: "{commondesktop}\YT-DL PLAI"; Filename: "{app}\YT-DL PLAI.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Creer un raccourci sur le Bureau"; GroupDescription: "Options :"

[Run]
Filename: "{app}\YT-DL PLAI.exe"; Description: "Lancer YT-DL PLAI maintenant"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
