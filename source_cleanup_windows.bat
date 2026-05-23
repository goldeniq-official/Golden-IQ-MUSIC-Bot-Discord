@echo off
setlocal
title Golden IQ MUSIC Bot - Cleanup
chcp 65001 >nul

cd /d "%~dp0"

echo ============================================================
echo  Golden IQ MUSIC Bot - Cleanup
echo ============================================================
echo.
echo This will delete the following from the project folder:
echo.
echo   Files       : Lavalink.jar
echo   Directories : venv, .app_commands_sync_data, .java, .jabba,
echo                 .db_cache, plugins, __pycache__
echo.
echo Your .env, config.json, lavalink.ini and local_database/ are NOT touched.
echo.
set /p "CONFIRM=Continue? [y/N] "
if /i not "%CONFIRM%"=="y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo [cleanup] Removing files...

if exist "Lavalink.jar" del /q /f "Lavalink.jar"

for %%D in (venv .app_commands_sync_data .java .jabba .db_cache plugins) do (
    if exist "%%D" (
        echo   - %%D
        rmdir /q /s "%%D"
    )
)

REM Recursive __pycache__ cleanup
for /d /r %%P in (__pycache__) do (
    if exist "%%P" rmdir /q /s "%%P"
)

echo.
echo [done] Cleanup finished successfully.
pause
endlocal
