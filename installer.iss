#define MyAppName "Database Sync Tool"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Moses Oghene"
#define MyAppURL "https://github.com/yourusername/database-sync-tool"
#define MyAppExeName "DatabaseSyncTool.exe"
#define MyAppId "{B8F4C8A0-8B4C-4C8A-8B4C-8B4C8A0B4C8A}"

[Setup]
AppId={{#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE.txt
InfoBeforeFile=README.txt
OutputDir=dist\installer
OutputBaseFilename=DatabaseSyncTool_Setup_v{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; FIXED: Changed to support Windows Server 2012 R2 (6.3) and later
MinVersion=6.3.9200
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoCopyright=Copyright (C) 2024 {#MyAppPublisher}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "startupicon"; Description: "Start {#MyAppName} automatically when Windows starts"; GroupDescription: "Startup Options"; Flags: unchecked
Name: "autostart"; Description: "Enable auto-sync on startup (requires startup icon)"; GroupDescription: "Startup Options"; Flags: unchecked

[Files]
; Main executable and Python runtime - FIXED PATHS
Source: "dist\DatabaseSyncTool\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\DatabaseSyncTool\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; Application assets
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "config.json.template"; DestDir: "{app}"; DestName: "config.json.template"; Flags: ignoreversion

; Documentation
Source: "README.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Registry]
; Add to Windows startup if requested
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DatabaseSyncTool"; ValueData: """{app}\{#MyAppExeName}"" --minimized --auto-sync"; Tasks: startupicon
; Store installation path for uninstaller
Root: HKLM; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
; File associations (optional)
Root: HKCR; Subkey: ".dbsync"; ValueType: string; ValueName: ""; ValueData: "DatabaseSyncConfig"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "DatabaseSyncConfig"; ValueType: string; ValueName: ""; ValueData: "Database Sync Configuration"; Flags: uninsdeletekey
Root: HKCR; Subkey: "DatabaseSyncConfig\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCR; Subkey: "DatabaseSyncConfig\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
; Optionally run the application after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop the application before uninstalling
Filename: "taskkill"; Parameters: "/F /IM {#MyAppExeName}"; RunOnceId: "StopApp"; Flags: runhidden

[UninstallDelete]
; Clean up any created files
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\*.bak"
Type: dirifempty; Name: "{app}\logs"
Type: dirifempty; Name: "{app}\backups"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile: String;
  ConfigTemplate: String;
  UserDataDir: String;
  UserConfigDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Create config template in installation directory
    ConfigTemplate := ExpandConstant('{app}\config.json.template');

    // User's config will be in %APPDATA%\Database Sync Tool\config.json
    UserConfigDir := ExpandConstant('{userappdata}\Database Sync Tool');
    UserDataDir := ExpandConstant('{localappdata}\Database Sync Tool');
    ConfigFile := UserConfigDir + '\config.json';

    // Create user directories
    ForceDirectories(UserConfigDir);
    ForceDirectories(UserDataDir);
    ForceDirectories(UserDataDir + '\logs');
    ForceDirectories(UserDataDir + '\backups');

    // Create initial config file in user directory if it doesn't exist
    if not FileExists(ConfigFile) and FileExists(ConfigTemplate) then
    begin
      FileCopy(ConfigTemplate, ConfigFile, False);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserConfigDir: String;
  UserDataDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Remove from startup registry if it was added manually
    RegDeleteValue(HKEY_CURRENT_USER, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 'DatabaseSyncTool');

    UserConfigDir := ExpandConstant('{userappdata}\Database Sync Tool');
    UserDataDir := ExpandConstant('{localappdata}\Database Sync Tool');

    // Ask if user wants to keep configuration and logs
    if MsgBox('Do you want to keep your configuration files and logs?' + #13#13 +
              'Select "No" to remove all application data.' + #13#13 +
              'Config location: ' + UserConfigDir + #13 +
              'Logs location: ' + UserDataDir,
              mbConfirmation, MB_YESNO or MB_DEFBUTTON1) = IDNO then
    begin
      // User chose to remove all data
      DelTree(UserConfigDir, True, True, True);
      DelTree(UserDataDir, True, True, True);
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);

  // FIXED: Updated version check to support Windows Server 2012 R2 and later
  // Windows Server 2012 R2 = 6.3, Windows 8.1 = 6.3
  if (Version.Major < 6) or ((Version.Major = 6) and (Version.Minor < 3)) then
  begin
    MsgBox('This application requires Windows Server 2012 R2, Windows 8.1, or later.' + #13#13 +
           'Current version: ' + IntToStr(Version.Major) + '.' + IntToStr(Version.Minor) + #13#13 +
           'Your current Windows version: ' + IntToStr(Version.Major) + '.' + IntToStr(Version.Minor) + '.' + IntToStr(Version.Build) + #13 +
           'Please update your Windows installation and try again.',
           mbError, MB_OK);
    Result := False;
  end
  else
  begin
    Result := True;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;