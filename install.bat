@echo off
title pyRevit + Arie Extension Installer

echo ================================
echo Downloading pyRevit v5.2.0
echo ================================

set "URL=https://github.com/pyrevitlabs/pyRevit/releases/download/v5.2.0.25181%%2B1332/pyRevit_5.2.0.25181_signed.exe"
set "FILE=%USERPROFILE%\Downloads\pyRevit_5.2.0.25181_signed.exe"

curl -L --fail "%URL%" -o "%FILE%"
if errorlevel 1 (
    echo Download failed.
    pause
    exit /b 1
)

echo File downloaded:
echo %FILE%
dir "%FILE%"
echo.

echo ================================
echo Running Installer
echo ================================
start /wait "" "%FILE%"

echo ================================
echo Checking pyRevit CLI
echo ================================
pyrevit -V
if %errorlevel% neq 0 (
    echo pyRevit CLI not found.
    echo Close and reopen Command Prompt, then run this script again.
    pause
    exit /b 1
)

echo ================================
echo Installing Arie Extension
echo ================================
pyrevit extend ui ArieProd https://github.com/klayza/Arie.git --dest "%appdata%\pyRevit\Extensions" --branch prod --debug

echo ================================
echo Done
echo ================================
echo Open Revit (make sure it was closed during install).
echo Go to pyRevit tab and click Reload.
echo Look for "Sargenti" tab.

pause