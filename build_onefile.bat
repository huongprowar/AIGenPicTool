@echo off
REM ================================================
REM Build Script - Single EXE File
REM ================================================

echo ================================================
echo   AI Image Generator - Build Single EXE
echo ================================================
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Clean previous builds
echo Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist\AIImageGenerator.exe" del "dist\AIImageGenerator.exe"

REM Build single executable
echo.
echo Building single executable...
echo This will take several minutes...
echo.

pyinstaller --onefile ^
    --windowed ^
    --name "AIImageGenerator" ^
    --hidden-import=PySide6.QtCore ^
    --hidden-import=PySide6.QtGui ^
    --hidden-import=PySide6.QtWidgets ^
    --hidden-import=openai ^
    --hidden-import=google.generativeai ^
    --hidden-import=httpx ^
    --hidden-import=pydantic ^
    --hidden-import=ui ^
    --hidden-import=ui.main_window ^
    --hidden-import=ui.create_tab ^
    --hidden-import=ui.settings_tab ^
    --hidden-import=ui.image_item ^
    --hidden-import=services ^
    --hidden-import=services.config_service ^
    --hidden-import=services.chatgpt_service ^
    --hidden-import=services.gemini_service ^
    --hidden-import=utils ^
    --hidden-import=utils.prompt_parser ^
    --hidden-import=utils.image_downloader ^
    --hidden-import=UnlimitedAPI ^
    --hidden-import=UnlimitedAPI.providers ^
    --hidden-import=UnlimitedAPI.providers.google_flow ^
    --exclude-module=tkinter ^
    --exclude-module=matplotlib ^
    --exclude-module=numpy ^
    --clean ^
    --noconfirm ^
    main.py

REM Check if build succeeded
if exist "dist\AIImageGenerator.exe" (
    echo.
    echo ================================================
    echo   BUILD SUCCESSFUL!
    echo ================================================
    echo.
    echo Single executable: dist\AIImageGenerator.exe
    echo File size:
    for %%A in ("dist\AIImageGenerator.exe") do echo   %%~zA bytes
    echo.
    echo Note: First startup may be slower as it extracts files.
    echo.
) else (
    echo.
    echo ================================================
    echo   BUILD FAILED!
    echo ================================================
)

pause
