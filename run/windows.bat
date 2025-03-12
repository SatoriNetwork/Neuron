REM this isn't used because we compile the batch file into the exe instead of telling it to trigger the bat file... but in theory we could use this instead
@echo off
title Satori Neuron
:restart
start "docker" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
:wait_for_docker
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    timeout /T 5 > NUL
    echo Waiting for Docker to start ...
    goto wait_for_docker
)
docker stop satorineuron >nul 2>&1
docker pull satorinet/satorineuron:latest
start http://localhost:24601
docker run --rm -it --name satorineuron --cpus="0.9" -p 24600:24600 -p 24601:24601 -v "%APPDATA%\Satori\run:/Satori/Neuron/run" -v "%APPDATA%\Satori\wallet:/Satori/Neuron/wallet" -v "%APPDATA%\Satori\config:/Satori/Neuron/config" -v "%APPDATA%\Satori\data:/Satori/Neuron/data" -v "%APPDATA%\Satori\models:/Satori/Neuron/models" --env ENV=prod satorinet/satorineuron:latest ./start.sh
echo.
if %ERRORLEVEL% EQU 0 (
    echo Container shutting down
    exit
) else if %ERRORLEVEL% EQU 1 (
    echo Restarting and updating Container
    goto restart
) else if %ERRORLEVEL% EQU 2 (
    REM this should never be seen as it is intercepted by app.py and handled to just restart satori within the container
    echo Restarting and updating Container
    goto restart
) else if %ERRORLEVEL% EQU 125 (
    echo Docker daemon error - possibly shutdown
    pause
) else if %ERRORLEVEL% EQU 137 (
    echo Container was killed - possibly out of memory
    pause
) else if %ERRORLEVEL% EQU 126 (
    echo Command cannot be invoked
    pause
) else if %ERRORLEVEL% EQU 127 (
    echo Command not found
    pause
) else if %ERRORLEVEL% EQU 130 (
    echo Container was terminated by Ctrl+C
    pause
) else if %ERRORLEVEL% EQU 143 (
    echo Container received shutdown request
    pause
) else (
    echo Unknown error code: %ERRORLEVEL%
    pause
)
