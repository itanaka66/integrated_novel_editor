; Integrated Novel Editor (INE) — Docker-free Windows installer
;
; Unlike installer\windows\ine.iss (which bundles docker-compose.release.yml
; and needs Docker Desktop), this bundles everything INE needs to run as
; plain Windows processes: a frozen ine-api.exe (Python + SQLite instead of
; PostgreSQL — see apps/api/desktop_main.py), the Next.js app running under
; a bundled portable node.exe, and a bundled qdrant.exe for semantic search.
; Ollama is still a separate prerequisite — it isn't bundled either way.
;
; Build: installer\windows-nodocker\build.ps1 (assembles payload\, then
; wraps `iscc ine-nodocker.iss`)
; Requires: Inno Setup 6 (https://jrsoftware.org/isinfo.php)

#define AppName "Integrated Novel Editor (INE) — No Docker"
#define AppVersion "0.6.0"
#define AppPublisher "INE"

[Setup]
AppId={{7C1E4B3F-9A52-4D6C-8B0E-1F3A6D9C2E48}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\INE-NoDocker
DefaultGroupName=INE (No Docker)
OutputDir=..\..\dist
OutputBaseFilename=INE-NoDocker-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; No administrator rights required — everything here is plain files plus
; user-mode processes (no service install, no driver, no Docker).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\launch.ps1

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"

[CustomMessages]
japanese.LaunchSetup=今すぐ起動する
english.LaunchSetup=Launch now
japanese.CreateDesktopIcon=デスクトップにショートカットを作成する
english.CreateDesktopIcon=Create a desktop shortcut

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "payload\ine-api.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\qdrant.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\node.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\web\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "payload\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\launch.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\stop.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\INEを起動"; Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launch.ps1"""; WorkingDir: "{app}"
Name: "{group}\INEを停止"; Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\stop.ps1"""; WorkingDir: "{app}"
Name: "{autodesktop}\INE (No Docker)"; Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launch.ps1"""; \
    Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launch.ps1"""; \
    Description: "{cm:LaunchSetup}"; Flags: postinstall skipifsilent nowait

[UninstallDelete]
; .env holds the generated admin password and any connection overrides —
; kept so a reinstall doesn't force re-entry. .\data\ (SQLite database,
; Qdrant storage, episode text mirror) and .\logs\ are deliberately left
; alone by the uninstaller either way; remove them by hand for a full wipe.
Type: files; Name: "{app}\.pids"
