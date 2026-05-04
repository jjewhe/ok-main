@echo off
pushd "%~dp0"
setlocal enabledelayedexpansion
echo [OMEGA] Initializing Clean Standalone EXE Build...

:: 1. Deep Clean
echo [OMEGA] Removing old artifacts...
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
if exist "omega_core.exe" del /f /q "omega_core.exe"
if exist "omega_core.spec" del /f /q "omega_core.spec"

:: 2. Check for PyInstaller and Requirements
echo [OMEGA] Installing agent requirements...
pip install -r requirements_agent.txt
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller not found. Installing...
    pip install pyinstaller
)

:: 3. Bundling
echo [OMEGA] Bundling Optimized Agent Core...
pyinstaller --noconfirm --onefile --windowed ^
    --add-data "core;core" ^
    --add-data "modules;modules" ^
    --hidden-import websockets ^
    --hidden-import cv2 ^
    --hidden-import mss ^
    --hidden-import psutil ^
    --hidden-import pynput ^
    --hidden-import numpy ^
    --hidden-import sounddevice ^
    --hidden-import pygrabber ^
    --hidden-import pygame ^
    --hidden-import PyTurboJPEG ^
    --hidden-import comtypes ^
    --hidden-import win32api ^
    --hidden-import win32gui ^
    --hidden-import win32con ^
    --hidden-import win32process ^
    --hidden-import winreg ^
    --hidden-import Cryptodome ^
    --hidden-import Cryptodome.Cipher.AES ^
    --hidden-import sqlite3 ^
    --hidden-import PyQt5.QtCore ^
    --hidden-import PyQt5.QtGui ^
    --hidden-import PyQt5.QtWidgets ^
    --name omega_core ^
    omega_core.py

:: 4. Finalize
if %errorlevel% equ 0 (
    echo [SUCCESS] Build complete!
    if exist "dist\omega_core.exe" (
        move /y "dist\omega_core.exe" "."
        echo Optimized EXE moved to root: omega_core.exe
    )
) else (
    echo [ERROR] Build failed.
)
