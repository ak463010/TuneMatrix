!ifndef APP_VERSION
!define APP_VERSION "0.1.0"
!endif

!ifndef DIST_DIR
!define DIST_DIR "..\..\dist\TuneMatrix"
!endif

!ifndef OUTPUT_DIR
!define OUTPUT_DIR "..\..\release-artifacts"
!endif

!include "MUI2.nsh"

Name "TuneMatrix"
OutFile "${OUTPUT_DIR}\TuneMatrix-${APP_VERSION}-windows-x64-setup.exe"
InstallDir "$LOCALAPPDATA\TuneMatrix"
InstallDirRegKey HKCU "Software\TuneMatrix" "InstallDir"
RequestExecutionLevel user

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "TuneMatrix" SEC_TUNEMATRIX
  SetOutPath "$INSTDIR"
  File /r "${DIST_DIR}\*"
  WriteRegStr HKCU "Software\TuneMatrix" "InstallDir" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\TuneMatrix"
  CreateShortcut "$SMPROGRAMS\TuneMatrix\TuneMatrix.lnk" "$INSTDIR\TuneMatrix.exe"
  CreateShortcut "$DESKTOP\TuneMatrix.lnk" "$INSTDIR\TuneMatrix.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\TuneMatrix.lnk"
  Delete "$SMPROGRAMS\TuneMatrix\TuneMatrix.lnk"
  RMDir "$SMPROGRAMS\TuneMatrix"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\TuneMatrix"
SectionEnd
