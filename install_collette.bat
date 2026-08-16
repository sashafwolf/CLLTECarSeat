@echo off
setlocal EnableExtensions EnableDelayedExpansion
TITLE Collette Vi Makana - First-Time Setup
ECHO ===================================================
ECHO   Collette Setup
ECHO ===================================================
ECHO.

:: --- 1. Locate a Python interpreter ---
ECHO [1/4] Locating Python...
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
    ECHO [ERROR] No Python interpreter found on PATH ^(and no Python 3.11 via the py launcher^).
    ECHO          Install Python 3.11+ from python.org first, then re-run this script.
    pause
    endlocal
    exit /b 1
)
ECHO       Using: %PYEXE%
ECHO.

:: --- 2. Install dependencies ---
ECHO [2/4] Installing dependencies from requirements.txt...
"%PYEXE%" -m pip install --upgrade pip >nul
"%PYEXE%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    ECHO [ERROR] pip install failed -- check the output above.
    pause
    endlocal
    exit /b 1
)
ECHO.

:: --- 3. Create .env template if missing (never overwrites a real one) ---
ECHO [3/4] Checking for .env...
if exist "%~dp0.env" (
    ECHO       .env already exists -- leaving it alone.
) else (
    ECHO       Creating a blank .env template. Fill in real values before first boot.
    (
        ECHO DISCORD_BOT_TOKEN=
        ECHO DISCORD_WEBHOOK_URL=
        ECHO TWITCH_OAUTH_TOKEN=
        ECHO TWITCH_CHANNEL_NAME=
        ECHO TWITCH_CLIENT_ID=
        ECHO TWITCH_CLIENT_SECRET=
        ECHO TWITCH_BOT_ID=
        ECHO GEMINI_API_KEY=
        ECHO ANTHROPIC_API_KEY=
        ECHO COLLETTE_BRAIN_MODE=ollama
        ECHO CLAUDE_MODEL=
        ECHO OPENROUTER_API_KEY=
        ECHO OPENROUTER_MODEL=
        ECHO JIRA_BASE_URL=
        ECHO JIRA_EMAIL=
        ECHO JIRA_API_TOKEN=
        ECHO JIRA_DEFAULT_PROJECT=
        ECHO JIRA_DEFAULT_ISSUE_TYPE=Task
    ) > "%~dp0.env"
    ECHO       Wrote .env -- open it and fill in real values.
)
ECHO.

ECHO [4/4] Setup complete.
ECHO       Next steps:
ECHO         1. Fill in .env with real API keys / tokens ^(see CLLTECarryOn.md, Tier 3^).
ECHO         2. If restoring from a backup, copy Tier 2 files ^(see CLLTECarryOn.md^) into place now.
ECHO         3. Run Boot_Collette.bat.
ECHO.
pause
endlocal
exit /b 0
