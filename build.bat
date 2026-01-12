@echo off
REM ================================================
REM Build Script for AI Image Generator
REM ================================================

echo ================================================
echo   AI Image Generator - Build Script
echo ================================================
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found. Using system Python.
)

REM Install/upgrade dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
echo.
echo Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM Build the application
echo.
echo Building application...
echo This may take a few minutes...
echo.

pyinstaller AIImageGenerator.spec --clean --noconfirm

REM Check if build succeeded
if exist "dist\AIImageGenerator\AIImageGenerator.exe" (
    echo.
    echo ================================================
    echo   BUILD SUCCESSFUL!
    echo ================================================
    echo.
    echo Output directory: dist\AIImageGenerator\
    echo Executable: dist\AIImageGenerator\AIImageGenerator.exe
    echo.
    echo To distribute:
    echo   1. Copy the entire 'dist\AIImageGenerator' folder
    echo   2. Run AIImageGenerator.exe on the target machine
    echo.
) else (
    echo.
    echo ================================================
    echo   BUILD FAILED!
    echo ================================================
    echo.
    echo Check the error messages above for details.
)

pause
