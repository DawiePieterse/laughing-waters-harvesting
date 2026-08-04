@echo off
:: Laughing Waters Harvesting - double-click this file to pull the latest
:: code from GitHub, install any new dependencies, and restart the server
:: so the update actually takes effect. See MANUAL.md chapter 2
:: ("Pulling future updates") for what this automates and does manually.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This needs administrator rights to restart the server - requesting them now...
    echo If Windows shows a User Account Control prompt, click "Yes".
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo.
echo ==> Pulling latest code from GitHub...
git pull
if %errorLevel% neq 0 (
    echo.
    echo Git pull failed - check the error above ^(no internet, a merge
    echo conflict, or this folder isn't a git checkout^). The server has
    echo NOT been restarted, so it's still running whatever it was before.
    pause
    exit /b 1
)

echo.
echo ==> Installing any new dependencies...
call "%~dp0backend\.venv\Scripts\activate.bat"
pip install --quiet --disable-pip-version-check -r "%~dp0backend\requirements.txt"
if %errorLevel% neq 0 (
    echo Warning: dependency install had a problem - continuing anyway, since
    echo most updates don't change requirements.txt. Check the error above if
    echo the server fails to start next.
)

echo.
echo ==> Restarting the server...
schtasks /query /tn "Laughing Waters Server" >nul 2>&1
if %errorLevel% equ 0 (
    schtasks /end /tn "Laughing Waters Server" >nul 2>&1
    timeout /t 2 /nobreak >nul
    schtasks /run /tn "Laughing Waters Server" >nul 2>&1
    echo Server restarted.
) else (
    echo Could not find the "Laughing Waters Server" scheduled task - if
    echo you're running the server manually in its own window instead,
    echo close and reopen that window yourself to pick up the update.
)

echo.
echo ==> Done. Remember: each phone still needs its app fully closed and
echo     reopened ^(not just backgrounded^) to pick up the new version -
echo     see MANUAL.md chapter 12 if a device still shows an old version.
echo.
pause
