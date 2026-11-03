@echo off
title Auto Proses Data iPos 4.0 Assistant
cd /d "%~dp0"

:: Cek Hak Akses Administrator (Wajib untuk mengontrol iPos 4.0 yang berjalan sebagai Admin)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Memerlukan hak akses Administrator untuk mengontrol iPos 4.0...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~dpnx0\"\"' -Verb RunAs"
    exit /b
)

echo ========================================================
echo   Auto Proses Data Bulanan & Tahunan iPos 4.0
echo ========================================================
echo.

:: Cek Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak terdeteksi di sistem PATH!
    echo Silakan install Python 3.10+ dari python.org.
    pause
    exit /b 1
)

:: Jalankan GUI
echo Menjalankan aplikasi floating bot (Administrator Mode)...
python gui.py

if %errorlevel% neq 0 (
    echo.
    echo Aplikasi ditutup dengan status error / interupsi.
    pause
)
