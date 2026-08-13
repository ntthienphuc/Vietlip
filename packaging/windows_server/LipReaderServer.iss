#ifndef StageDir
  #define StageDir "stage\server"
#endif
#ifndef OutputDir
  #define OutputDir "output"
#endif

[Setup]
AppId={{36744A13-654E-4D4B-A214-D36B7CC8D4A0}
AppName=Lip Reader Server
AppVersion=1.1.0
AppPublisher=Lip Reader
DefaultDirName={localappdata}\Programs\Lip Reader Server
DefaultGroupName=Lip Reader Server
OutputDir={#OutputDir}
OutputBaseFilename=LipReader-Server-Setup-v1.1.0
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\LipReaderServer.exe
UninstallDisplayName=Lip Reader Server 1.1.0
SetupLogging=yes
DiskSpanning=yes
DiskSliceSize=2100000000
SlicesPerDisk=1
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "localllm"; Description: "Enable local language assistance with Ollama + qwen2.5:7b (about 9 GB; optional)"; GroupDescription: "Language assistance:"; Flags: unchecked

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Lip Reader Server"; Filename: "{app}\LipReaderServer.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Lip Reader Server"; Filename: "{app}\LipReaderServer.exe"; WorkingDir: "{app}"
Name: "{group}\User guide"; Filename: "{app}\README_INSTALL.txt"
Name: "{group}\Uninstall Lip Reader Server"; Filename: "{uninstallexe}"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\tools\install_optional_llm.ps1"" -AppDir ""{app}"""; WorkingDir: "{app}"; Description: "Install Ollama and qwen2.5:7b"; Flags: waituntilterminated; Tasks: localllm
Filename: "{app}\LipReaderServer.exe"; Description: "Start Lip Reader Server"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /F /IM LipReaderServer.exe"; Flags: runhidden; RunOnceId: "StopLipReaderServer"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\ollama-models"
Type: filesandordirs; Name: "{localappdata}\Lip Reader Server"

[InstallDelete]
; Earlier internal builds used this checkpoint name. Remove only that exact
; obsolete payload during an in-place upgrade; never delete arbitrary models.
Type: files; Name: "{app}\resources\models\epoch=13-loss_val=53.8436-003.ckpt"

[Code]
function PathIsInside(const ParentPath, ChildPath: String): Boolean;
var
  NormalizedParent: String;
  NormalizedChild: String;
begin
  NormalizedParent := Uppercase(AddBackslash(ExpandFileName(ParentPath)));
  NormalizedChild := Uppercase(AddBackslash(ExpandFileName(ChildPath)));
  Result := Pos(NormalizedParent, NormalizedChild) = 1;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{cmd}'), '/c taskkill /F /IM LipReaderServer.exe', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  if UninstallSilent then
  begin
    Result := True;
  end
  else
  begin
    Result := MsgBox(
      'Gỡ Lip Reader Server và toàn bộ thành phần do ứng dụng quản lý?' +
      Chr(13) + Chr(10) + Chr(13) + Chr(10) +
      'Sẽ xóa server, checkpoint đi kèm, cấu hình, shortcut, log/cache và ' +
      'LLM/model nếu chúng nằm trong thư mục Lip Reader.' +
      Chr(13) + Chr(10) + Chr(13) + Chr(10) +
      'Ollama hoặc model đã có sẵn và đang dùng chung ngoài Lip Reader sẽ ' +
      'được giữ lại.' +
      Chr(13) + Chr(10) + Chr(13) + Chr(10) +
      'Bạn có muốn tiếp tục không?',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ModelsPath: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    if RegQueryStringValue(HKCU, 'Environment', 'OLLAMA_MODELS', ModelsPath) and
       PathIsInside(ExpandConstant('{app}'), ModelsPath) then
    begin
      RegDeleteValue(HKCU, 'Environment', 'OLLAMA_MODELS');
    end;
  end;
end;
