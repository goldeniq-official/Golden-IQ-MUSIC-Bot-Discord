@echo off
setlocal EnableDelayedExpansion
title Golden IQ MUSIC Bot - Startup
chcp 65001 >nul

cd /d "%~dp0"

echo ============================================================
echo  Golden IQ MUSIC Bot - Windows Launcher
echo ============================================================
echo.

REM ---- Detect Python ------------------------------------------------------
set "PYTHON_CMD="
python3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
) else (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
    ) else (
        python --version >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_CMD=python"
        )
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python was not found on PATH.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%v"
echo [info] Using %PY_VER%

REM ---- Java check (informational) ----------------------------------------
java -version >nul 2>&1
if errorlevel 1 (
    echo [info] Java not detected on PATH.
    echo        The bot will auto-download JDK on first run if it needs Lavalink locally.
) else (
    for /f "tokens=3" %%j in ('java -version 2^>^&1 ^| findstr /i "version"') do set "JAVA_VER=%%j"
    echo [info] Java detected: !JAVA_VER!
)

REM ---- Virtual environment ------------------------------------------------
if not exist "venv\Scripts\activate.bat" (
    echo [setup] Creating virtual environment...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )

    call "venv\Scripts\activate.bat"
    if errorlevel 1 (
        echo [ERROR] Failed to activate virtual environment.
        pause
        exit /b 1
    )

    echo [setup] Upgrading pip...
    python -m pip install --upgrade pip wheel setuptools

    echo [setup] Installing dependencies (this can take several minutes)...
    pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. See output above for details.
        pause
        exit /b 1
    )
) else (
    call "venv\Scripts\activate.bat"
    if errorlevel 1 (
        echo [ERROR] Failed to activate existing venv. Delete the "venv" folder and rerun.
        pause
        exit /b 1
    )
)

REM ---- .env check ---------------------------------------------------------
if not exist ".env" (
    if exist ".example.env" (
        echo [info] No .env found. Copying .example.env -^> .env
        copy /Y ".example.env" ".env" >nul
        echo [warn] Edit .env and set your TOKEN before the bot can log in.
    )
)

REM ---- Restart loop -------------------------------------------------------
echo.
echo [run] Starting bot (Ctrl+C to stop)...
echo ============================================================
echo.

:restart_loop
python main.py
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
    echo.
    echo [info] Bot exited cleanly. Goodbye.
    goto :end
)

echo.
echo [warn] Bot exited with code %EXIT_CODE%. Restarting in 5 seconds...
echo        Press Ctrl+C now to abort the restart loop.
timeout /t 5 /nobreak >nul
if errorlevel 1 goto :end
goto :restart_loop

:end
pause
endlocal
