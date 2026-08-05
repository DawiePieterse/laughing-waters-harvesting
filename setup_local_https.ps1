# Laughing Waters Harvesting - local HTTPS for field/pack house devices.
#
# Field and Pack House phones only need HTTPS to satisfy the browser's
# camera-access rule (see MANUAL.md, "Enabling the QR camera scanner") -
# they never actually need to leave the farm's own Wi-Fi. Routing them
# through Tailscale for that made them depend on an always-on background
# VPN connection, which Android's battery management fights constantly.
#
# This script gives them HTTPS directly over the LAN instead: it creates a
# private local certificate authority (via mkcert), issues this server a
# certificate for its own LAN IP, and starts a second server process
# (alongside the existing plain-HTTP one - this doesn't touch that at all)
# that serves HTTPS on port 8443 using it. Each phone then needs the CA's
# public certificate installed as trusted, once - not a running connection,
# just a one-time decision the phone remembers permanently.
#
# Run via setup_local_https.bat, which handles administrator elevation.
# Safe to re-run - regenerates the certificate and re-registers the task.

$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$ToolsDir = Join-Path $RepoRoot "tools"
$MkcertExe = Join-Path $ToolsDir "mkcert.exe"
$MkcertVersion = "1.4.4"
$MkcertUrl = "https://github.com/FiloSottile/mkcert/releases/download/v$MkcertVersion/mkcert-v$MkcertVersion-windows-amd64.exe"
$CaDir = Join-Path $RepoRoot "certs\ca"
$LeafDir = Join-Path $RepoRoot "certs\leaf"
$PublicDir = Join-Path $RepoRoot "certs\public"
$HttpsPort = 8443
$TaskName = "Laughing Waters Server (Local HTTPS)"
$FirewallRuleName = "Laughing Waters Server (Local HTTPS)"

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "    $msg" -ForegroundColor Red }

try {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Err "This script needs to run as Administrator."
        Write-Err "Please run setup_local_https.bat instead of this file directly - it handles that automatically."
        exit 1
    }

    if (-not (Test-Path $VenvPython)) {
        Write-Err "backend\.venv not found - run install.bat first to set up the server itself."
        exit 1
    }

    Write-Host ""
    Write-Host "Laughing Waters Harvesting - Local HTTPS Setup" -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan

    # --- Step 1: Find this PC's LAN address ---
    Write-Step "Finding this PC's network address..."
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.PrefixOrigin -ne "WellKnown" } |
        Select-Object -First 1 -ExpandProperty IPAddress
    if (-not $ip) {
        Write-Err "Could not auto-detect this PC's LAN IP address."
        Write-Err "Make sure it's connected to the network, then re-run this script."
        exit 1
    }
    Write-Ok "Certificate will cover: $ip"
    Write-Warn "If this PC's IP ever changes (no static IP / DHCP reservation set),"
    Write-Warn "re-run this script to issue a fresh certificate for the new address."

    # --- Step 2: Get mkcert ---
    Write-Step "Checking for mkcert..."
    New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null
    if (-not (Test-Path $MkcertExe)) {
        Write-Warn "mkcert not found - downloading v$MkcertVersion..."
        Invoke-WebRequest -Uri $MkcertUrl -OutFile $MkcertExe -UseBasicParsing
        Write-Ok "Downloaded mkcert"
    } else {
        Write-Ok "mkcert already present"
    }

    # --- Step 3: Create (or reuse) the local certificate authority ---
    Write-Step "Setting up the local certificate authority..."
    New-Item -ItemType Directory -Force -Path $CaDir | Out-Null
    New-Item -ItemType Directory -Force -Path $LeafDir | Out-Null
    New-Item -ItemType Directory -Force -Path $PublicDir | Out-Null
    $env:CAROOT = $CaDir
    & $MkcertExe -install
    if ($LASTEXITCODE -ne 0) {
        Write-Err "mkcert -install failed - see the error above."
        exit 1
    }
    Write-Ok "Local CA trusted by this PC (this only affects browsing on this PC itself, not phones)"

    # --- Step 4: Issue this server a certificate ---
    Write-Step "Issuing a certificate for $ip..."
    $certFile = Join-Path $LeafDir "server.pem"
    $keyFile = Join-Path $LeafDir "server-key.pem"
    & $MkcertExe -cert-file $certFile -key-file $keyFile $ip localhost 127.0.0.1
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Certificate generation failed - see the error above."
        exit 1
    }
    Copy-Item -Path (Join-Path $CaDir "rootCA.pem") -Destination (Join-Path $PublicDir "rootCA.pem") -Force
    Write-Ok "Certificate issued and the CA's public certificate made available for phones to download"

    # --- Step 5: Write the HTTPS launcher script ---
    Write-Step "Creating the HTTPS server launcher..."
    $launcherPath = Join-Path $RepoRoot "start_server_https.bat"
    $launcherContent = @"
@echo off
cd /d "$BackendDir"
"$VenvPython" -m uvicorn main:app --host 0.0.0.0 --port $HttpsPort --ssl-certfile "$certFile" --ssl-keyfile "$keyFile"
"@
    Set-Content -Path $launcherPath -Value $launcherContent -Encoding ASCII
    Write-Ok "Created $launcherPath"

    # --- Step 6: Firewall rule ---
    Write-Step "Allowing the app through Windows Firewall on port $HttpsPort..."
    netsh advfirewall firewall delete rule name="$FirewallRuleName" | Out-Null
    netsh advfirewall firewall add rule name="$FirewallRuleName" dir=in action=allow protocol=TCP localport=$HttpsPort | Out-Null
    Write-Ok "Firewall rule set for port $HttpsPort"

    # --- Step 7: Scheduled task (runs alongside the existing plain-HTTP server) ---
    Write-Step "Registering the HTTPS server to start automatically with Windows..."
    schtasks /query /tn "$TaskName" >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        schtasks /end /tn "$TaskName" >$null 2>&1
        Start-Sleep -Seconds 1
        schtasks /delete /tn "$TaskName" /f | Out-Null
    }
    schtasks /create /tn "$TaskName" /tr "`"$launcherPath`"" /sc onstart /ru SYSTEM /rl highest /f | Out-Null
    Write-Ok "Scheduled task '$TaskName' registered"

    # --- Step 8: Start it now ---
    Write-Step "Starting the HTTPS server now..."
    schtasks /run /tn "$TaskName" | Out-Null
    Start-Sleep -Seconds 3
    Write-Ok "Server starting in the background"

    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host " Setup complete!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host " Field/Pack House devices should now use:  https://${ip}:${HttpsPort}/"
    Write-Host ""
    Write-Host " Before that works on a phone, install this server's certificate as"
    Write-Host " trusted on it, once. The file to install is:"
    Write-Host "   $PublicDir\rootCA.pem"
    Write-Host " or download it directly from a phone on the farm Wi-Fi at:"
    Write-Host "   http://${ip}:8000/certs/rootCA.pem"
    Write-Host ""
    Write-Host " See MANUAL.md chapter 2, 'Local HTTPS for field/pack house devices',"
    Write-Host " for the exact install-certificate steps per phone."
} catch {
    Write-Host ""
    Write-Err "Something went wrong:"
    Write-Err $_.Exception.Message
    exit 1
}
