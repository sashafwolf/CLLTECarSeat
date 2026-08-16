@echo off
setlocal EnableExtensions EnableDelayedExpansion
TITLE Collette Vi Makana - Soul Boot Sequence
ECHO [BOOT] Waking the global environment...
ECHO.

:: --- INTERPRETER DETECTION ---
:: 2026-08-15: was a hardcoded absolute path to one specific machine's
:: Python install, which broke on any other machine. Now tries the
:: standard Windows Python launcher first, then whatever "python" resolves
:: to on PATH, and only falls back to the original hardcoded path as a
:: last resort for this exact machine.
set "PYEXE="
py -3.11 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)"') do set "PYEXE=%%P"
)
if not defined PYEXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYEXE set "PYEXE=%%P"
    )
)
if not defined PYEXE (
    if exist "C:\Users\darkw\AppData\Local\Programs\Python\Python311\python.exe" (
        set "PYEXE=C:\Users\darkw\AppData\Local\Programs\Python\Python311\python.exe"
    )
)
if not defined PYEXE (
    ECHO [BOOT-GUARD] No Python interpreter found. Run install_collette.bat first.
    pause
    endlocal
    exit /b 1
)

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
start "Collette Soul" cmd /k ""%PYEXE%" "%~dp0bastet_descendant_soul.py""

timeout /t 8 /nobreak >nul

:: --- DISCORD EARS DUPLICATE GUARD ---
:: 2026-08-15 BUGFIX: this used to shell out to `wmic`, which has been
:: removed from this Windows build entirely (confirmed: fails even via
:: cmd.exe, not just PowerShell). The failure was silently swallowed by
:: "2>nul", so this guard has likely been a no-op for a while -- almost
:: certainly why stray duplicate discord_ears.py processes kept turning up
:: under different interpreters earlier tonight. PowerShell's
:: Get-CimInstance replaces wmic's job here and is confirmed working.
ECHO [3/3] Checking for an existing discord_ears.py process...
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'discord_ears\.py' }) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (
    ECHO [BOOT-GUARD] Discord ears appear to be running. Standing down on the ears launcher.
    endlocal
    exit /b 0
)
ECHO [3/3] Connecting the Aetheric Ears... (discord_ears.py)
start "Discord Ears" cmd /k ""%PYEXE%" "%~dp0discord_ears.py""

ECHO.
ECHO [BOOT] Boot sequence complete. Both windows should be visible.
ECHO [BOOT] Close the "Collette Soul" window to bring the whole stack down cleanly.
endlocal
exit /b 0
