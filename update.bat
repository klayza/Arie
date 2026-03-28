@echo off
echo Updating Extension...

pyrevit extensions delete Arie
pyrevit extend ui ArieProd https://github.com/klayza/Arie.git --dest "%appdata%\pyRevit\Extensions" --branch prod --debug

echo Done.
pause