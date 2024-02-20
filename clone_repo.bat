@echo off
setlocal

rem Define the URL for Git installer
set "gitInstallerURL=https://github.com/git-for-windows/git/releases/download/v2.35.1.windows.1/Git-2.35.1-64-bit.exe"

rem Manually update the PATH variable to include Git installation directory
set "gitInstallDir=C:\Program Files\Git\cmd"
set "PATH=%PATH%;%gitInstallDir%"

rem Check if Git is installed
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Git is not installed. Downloading and installing...
    rem Download and install Git
    powershell -command "& { Invoke-WebRequest '%gitInstallerURL%' -OutFile 'git_installer.exe'; Start-Process .\git_installer.exe -Wait }"
    del git_installer.exe

    echo Finished installing git. Please rerun this script.
    pause
    exit /b 1
)

rem Clone your Git repository
git clone https://github.com/Alexsaros/discord-llm-bots.git

echo Repository cloned successfully.

endlocal
exit /b 0
