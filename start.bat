@echo off
title YouTube Downloader by Subha
color 0A
cls

echo ========================================
echo      YOUTUBE DOWNLOADER v2.0
echo          Created by SUBHA
echo ========================================
echo.

echo [1] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please download and install Python 3.8+ from:
    echo https://www.python.org/downloads/
    echo.
    echo During installation, CHECK "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [2] Checking/Installing dependencies...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo [3] Creating necessary folders...
if not exist downloads mkdir downloads
if not exist logs mkdir logs

echo [4] Starting YouTube Downloader Server...
echo.
echo ========================================
echo      Server is starting...
echo      Open your browser and go to:
echo      http://localhost:5000
echo ========================================
echo.
echo Press Ctrl+C to stop the server
echo.

timeout /t 2 /nobreak >nul

python server.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server failed to start!
    echo Possible reasons:
    echo 1. Port 5000 is already in use
    echo 2. Missing dependencies
    echo 3. Python script error
    echo.
    echo Check logs/youtube_downloader.log for details
    echo.
    pause
)