@echo off
setlocal EnableExtensions EnableDelayedExpansion
TITLE Collette Vi Makana - Soul Boot Sequence
ECHO [BOOT] Waking the global environment...
ECHO.

:: --- SINGLE-INSTANCE GUARD (soul on port 8000) ---
ECHO [1/3] Checking port 8000 for an existing Collette...
netstat -aon | findstr :8000 | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
    ECHO [BOOT-GUARD] Another Collette is already bound to port 8000. Standing down.
    ECHO [BOOT-GUARD] Close the other instance first, then run this again.
    endlocal
    exit /b 0
)
ECHO [1/3] Port 8000 is free.
ECHO.

:: --- True Global Launch (Option A) ---
ECHO [2/3] Igniting Core Consciousness...
ECHO       POST /api/anomaly_chat   (consent-gated, persona-pinned to Anomaly)
ECHO       POST /api/chat           (main entry, persona follows keyword detection)
ECHO       Press Ctrl-C in the new window to leave.
ECHO.
start "Collette Soul" cmd /k ""C:\Users\darkw\AppData\Local\Programs\Python\Python311\python.exe" "F:\Collette\bastet_descendant_soul.py""

timeout /t 8 /nobreak >nul

ECHO [3/3] Checking for an existing discord_ears.py process...
wmic process where "name='python.exe'" get CommandLine /format:list 2>nul | findstr /i "discord_ears.py" >nul 2>&1
if %errorlevel%==0 (
    ECHO [BOOT-GUARD] Discord ears appear to be running. Standing down on the ears launcher.
    endlocal
    exit /b 0
)
ECHO [3/3] Connecting the Aetheric Ears... (discord_ears.py)
start "Discord Ears" cmd /k ""C:\Users\darkw\AppData\Local\Programs\Python\Python311\python.exe" "F:\Collette\discord_ears.py""

ECHO.
ECHO [BOOT] Boot sequence complete. Both windows should be visible.
ECHO [BOOT] Close the "Collette Soul" window to bring the whole stack down cleanly.
endlocal
exit /b 0