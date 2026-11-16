#ifndef StageDir
  #error StageDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif

[Setup]
AppId=VietLip.Server
AppName=VietLip Server
AppVersion=1.10.1
AppPublisher=VietLip
DefaultDirName={localappdata}\Programs\VietLip Server
DefaultGroupName=VietLip
OutputDir={#OutputDir}
OutputBaseFilename=VietLip-Server-Setup-1.10.1
SetupIconFile={#StageDir}\VietLip.ico
UninstallDisplayIcon={app}\VietLip.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
DiskSpanning=yes
DiskSliceSize=2000000000
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=README_INSTALL.txt

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Excludes: "*.pyc,*.pyo,__pycache__"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{app}\server\app\services\llm_postprocessor.py"
Type: files; Name: "{app}\server\app\services\candidate_selector.py"
Type: files; Name: "{app}\server\app\services\__pycache__\llm_postprocessor.*.pyc"
Type: files; Name: "{app}\server\app\services\__pycache__\candidate_selector.*.pyc"

[Icons]
Name: "{group}\VietLip Server"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\server\desktop_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\VietLip.ico"
Name: "{autodesktop}\VietLip Server"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\server\desktop_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\VietLip.ico"; Tasks: desktopicon
Name: "{group}\VietLip - User guide"; Filename: "{app}\README_INSTALL.txt"

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\server\desktop_launcher.py"""; WorkingDir: "{app}"; Description: "Open VietLip Server"; Flags: nowait postinstall skipifsilent
