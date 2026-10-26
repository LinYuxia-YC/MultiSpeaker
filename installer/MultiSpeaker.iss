; MultiSpeaker installer (per-user, no UAC prompt needed).
#define MyAppName "MultiSpeaker"
#define MyAppVersion "1.1.1"
#define MyAppExeName "MultiSpeaker.exe"

[Setup]
AppId={{CEBD59FB-9BED-4158-9E87-BE80FEDB2A5E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} 多扬声器同步播放器
AppPublisher=MultiSpeaker
DefaultDirName={autopf}\MultiSpeaker
DefaultGroupName=MultiSpeaker
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=MultiSpeaker-Setup-{#MyAppVersion}
SetupIconFile=..\app\resources\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} 多扬声器同步播放器
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
ShowLanguageDialog=auto

RedirectionGuard=no
CloseApplications=no

[Languages]
Name: "cn"; MessagesFile: "ChineseSimplified.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"; Flags: checkedonce

[Files]
Source: "..\dist\MultiSpeaker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MultiSpeaker"; Filename: "{app}\{#MyAppExeName}"; Comment: "多扬声器同步播放器"
Name: "{group}\卸载 MultiSpeaker"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MultiSpeaker"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "多扬声器同步播放器"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 MultiSpeaker"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c reg delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v MultiSpeaker /f"; Flags: runhidden

[Registry]
Root: HKCU; Subkey: "Software\MultiSpeaker"; Flags: uninsdeletekey

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
