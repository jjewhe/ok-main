@echo off
set CSC_PATH=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set TARGET=omega_phantom.exe
set SOURCE=phantom_loader.cs

echo [OMEGA] Building Phantom Universal Loader...

if not exist %CSC_PATH% (
    echo [ERROR] C# Compiler not found at %CSC_PATH%
    pause
    exit /b
)

%CSC_PATH% /target:winexe /out:%TARGET% /reference:System.IO.Compression.FileSystem.dll /optimize+ %SOURCE%

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Phantom Loader built: %TARGET%
    echo Size: 
    for %%I in (%TARGET%) do echo %%~zI bytes
) else (
    echo [ERROR] Build failed.
)
pause
