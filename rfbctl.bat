@echo off
REM RFBooking FastAPI OSS - Windows Management Script
REM Copyright (C) 2025 Oleg Tokmakov
REM SPDX-License-Identifier: AGPL-3.0-or-later

setlocal enabledelayedexpansion

set CONTAINER_NAME=rfbooking
set DEFAULT_PORT=8000

:menu
cls
echo ============================================
echo   RFBooking FastAPI OSS - Management
echo ============================================
echo.
echo   [1] Start container
echo   [2] Stop container
echo   [3] Restart container
echo   [4] View status
echo   [5] View logs
echo   [6] Open in browser
echo   [7] Backup database
echo   [8] Exit
echo.
set /p choice="Select option (1-8): "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto status
if "%choice%"=="5" goto logs
if "%choice%"=="6" goto browser
if "%choice%"=="7" goto backup
if "%choice%"=="8" goto end

echo Invalid option. Press any key to try again...
pause >nul
goto menu

:start
echo.
echo Starting RFBooking...
docker-compose up -d
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to start. Is Docker Desktop running?
    pause
    goto menu
)
echo.
echo Container started successfully!
echo.
echo Waiting for services to initialize...
timeout /t 10 /nobreak >nul
echo.
echo Access RFBooking at: http://localhost:%DEFAULT_PORT%
echo.
pause
goto menu

:stop
echo.
echo Stopping RFBooking...
docker-compose down
echo.
echo Container stopped.
pause
goto menu

:restart
echo.
echo Restarting RFBooking...
docker restart %CONTAINER_NAME%
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Container not found or not running.
    pause
    goto menu
)
echo.
echo Container restarted. Waiting for services...
timeout /t 10 /nobreak >nul
echo Done!
pause
goto menu

:status
echo.
echo ============================================
echo   Container Status
echo ============================================
echo.
docker ps --filter "name=%CONTAINER_NAME%" --format "Name: {{.Names}}\nStatus: {{.Status}}\nPorts: {{.Ports}}"
if %errorlevel% neq 0 (
    echo Container is not running.
)
echo.
echo ============================================
echo   Service Status (inside container)
echo ============================================
echo.
docker exec %CONTAINER_NAME% supervisorctl status 2>nul
if %errorlevel% neq 0 (
    echo Unable to get service status. Container may not be running.
)
echo.
pause
goto menu

:logs
echo.
echo Showing container logs (press Ctrl+C to stop)...
echo.
docker logs -f %CONTAINER_NAME%
goto menu

:browser
echo.
echo Opening browser...
start http://localhost:%DEFAULT_PORT%
goto menu

:backup
echo.
set "BACKUP_FILE=rfbooking-backup-%date:~-4,4%%date:~-10,2%%date:~-7,2%-%time:~0,2%%time:~3,2%%time:~6,2%.db"
set "BACKUP_FILE=%BACKUP_FILE: =0%"
echo Creating backup: %BACKUP_FILE%
docker cp %CONTAINER_NAME%:/data/rfbooking.db "./%BACKUP_FILE%"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Backup failed. Is the container running?
) else (
    echo.
    echo Backup created successfully!
)
pause
goto menu

:end
echo.
echo Goodbye!
exit /b 0
