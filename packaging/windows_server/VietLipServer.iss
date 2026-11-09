#ifndef StageDir
  #error StageDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif

[Setup]
AppId=VietLip.Server
AppName=VietLip Server
AppVersion=1.6.3
AppPublisher=VietLip
DefaultDirName={localappdata}\Programs\VietLip Server
DefaultGroupName=VietLip
OutputDir={#OutputDir}
OutputBaseFilename=VietLip-Server-Setup-1.6.3
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
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VietLip Server"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\server\desktop_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\VietLip.ico"
Name: "{autodesktop}\VietLip Server"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\server\desktop_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\VietLip.ico"; Tasks: desktopicon
Name: "{group}\VietLip - User guide"; Filename: "{app}\README_INSTALL.txt"

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\server\desktop_launcher.py"""; WorkingDir: "{app}"; Description: "Open VietLip Server"; Flags: nowait postinstall skipifsilent
