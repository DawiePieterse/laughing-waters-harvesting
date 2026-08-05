@echo off
:: Laughing Waters Harvesting - double-click to set up local HTTPS for
:: field/pack house devices, so they don't need Tailscale running to use
:: the QR camera scanner. See MANUAL.md chapter 2, "Local HTTPS for
:: field/pack house devices", for what this does and the per-phone
:: certificate install steps needed afterward. Run install.bat first if
:: you haven't already - this needs the server's virtual environment.
::
:: Uses "-ExecutionPolicy Bypass" scoped to this one invocation only - it
:: does not change any system-wide setting.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This needs administrator rights - requesting them now...
    echo If Windows shows a User Account Control prompt, click "Yes".
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_local_https.ps1"
echo.
pause
