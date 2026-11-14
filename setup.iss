; setup.iss
; Arı Fırın Muhasebe Sistemi - Inno Setup 6 Kurulum Betiği
; Son kullanıcı ve istemci makinelerinde tam otomatik kurulum,
; masaüstü simgesi, başlat menüsü ve kaldırma (uninstaller) desteği sağlar.

#define MyAppName "Arı Fırın Muhasebe Sistemi"
#define MyAppVersion "1.0.5"
#define MyAppPublisher "Arı Fırın Bilişim"
#define MyAppExeName "AriFirin.exe"
#define MyAppIcon "resources\icons\app.ico"

[Setup]
AppId={{C47291B8-9D28-44A9-B101-57FE5329C142}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\AriFirin
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=AriFirin_Setup_v{#MyAppVersion}
SetupIconFile={#MyAppIcon}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Ana çalıştırılabilir ikili dosya
Source: "dist\AriFirin\AriFirin.exe"; DestDir: "{app}"; Flags: ignoreversion

; _internal klasörü (PyInstaller bağımlılıkları - ZORUNLU)
Source: "dist\AriFirin\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; Varsayılan yapılandırma şablonu (Kullanıcı yapılandırması varsa ezilmez)
Source: "config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

; Kaynak dosyaları, ikonlar ve şablonlar
Source: "resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\resources\icons\app.ico"
Name: "{group}\Kurulum ve Bağlantı Sihirbazı"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--setup"; IconFilename: "{app}\resources\icons\app.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\resources\icons\app.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
