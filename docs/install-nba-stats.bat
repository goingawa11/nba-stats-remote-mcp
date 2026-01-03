@echo off
setlocal enabledelayedexpansion

:: NBA Stats MCP Installer for Claude Desktop (Windows)
:: This script automatically configures Claude Desktop to use the NBA Stats server

cls
echo ==============================================
echo    NBA Stats for Claude Desktop - Installer
echo ==============================================
echo.

:: Check for Node.js
echo Checking prerequisites...
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo X Node.js is not installed!
    echo.
    echo Node.js is required to connect Claude Desktop to NBA Stats.
    echo Please install it from: https://nodejs.org/
    echo ^(Choose the LTS version^)
    echo.
    echo After installing Node.js, run this installer again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo √ Node.js is installed ^(%NODE_VERSION%^)

:: Check for npx
where npx >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo X npx is not available ^(should come with Node.js^)
    echo    Try reinstalling Node.js from https://nodejs.org/
    echo.
    pause
    exit /b 1
)
echo √ npx is available
echo.

:: Set config path
set "CONFIG_DIR=%APPDATA%\Claude"
set "CONFIG_FILE=%CONFIG_DIR%\claude_desktop_config.json"

echo Config location: %CONFIG_FILE%
echo.

:: Check if Claude Desktop config directory exists
if not exist "%CONFIG_DIR%" (
    echo Warning: Claude Desktop config directory not found.
    echo Have you installed and run Claude Desktop at least once?
    echo.
    echo Expected location: %CONFIG_DIR%
    echo.
    set /p CREATE_DIR="Would you like to create the directory? (y/n): "
    if /i "!CREATE_DIR!"=="y" (
        mkdir "%CONFIG_DIR%"
        echo √ Created config directory
    ) else (
        echo Installation cancelled.
        pause
        exit /b 1
    )
)

:: Check if nba-stats is already configured
if exist "%CONFIG_FILE%" (
    findstr /c:"nba-stats" "%CONFIG_FILE%" >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo √ NBA Stats is already configured!
        echo.
        echo If you're having issues, try:
        echo 1. Completely quit Claude Desktop
        echo 2. Reopen Claude Desktop
        echo.
        pause
        exit /b 0
    )
)

:: Backup existing config if it exists
if exist "%CONFIG_FILE%" (
    set "BACKUP_FILE=%CONFIG_FILE%.backup.%date:~-4,4%%date:~-10,2%%date:~-7,2%"
    copy "%CONFIG_FILE%" "!BACKUP_FILE!" >nul
    echo √ Backed up existing config
)

:: Check if we need to merge with existing config or create new
if exist "%CONFIG_FILE%" (
    findstr /c:"mcpServers" "%CONFIG_FILE%" >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo.
        echo Your config already has MCP servers configured.
        echo Adding NBA Stats to your existing configuration...
        echo.

        :: Use PowerShell to safely merge JSON
        powershell -Command ^
            "$config = Get-Content '%CONFIG_FILE%' | ConvertFrom-Json; " ^
            "if (-not $config.mcpServers) { $config | Add-Member -NotePropertyName 'mcpServers' -NotePropertyValue @{} }; " ^
            "$config.mcpServers | Add-Member -NotePropertyName 'nba-stats' -NotePropertyValue @{ " ^
            "    command = 'npx'; " ^
            "    args = @('mcp-remote', 'https://nba-stats-remote-mcp-production.up.railway.app/mcp') " ^
            "} -Force; " ^
            "$config | ConvertTo-Json -Depth 10 | Set-Content '%CONFIG_FILE%'"

        echo √ Added NBA Stats to existing configuration
    ) else (
        goto :createfresh
    )
) else (
    :createfresh
    echo Creating new Claude Desktop configuration...
    (
        echo {
        echo   "mcpServers": {
        echo     "nba-stats": {
        echo       "command": "npx",
        echo       "args": [
        echo         "mcp-remote",
        echo         "https://nba-stats-remote-mcp-production.up.railway.app/mcp"
        echo       ]
        echo     }
        echo   }
        echo }
    ) > "%CONFIG_FILE%"
    echo √ Configuration created
)

echo.
echo ==============================================
echo    √ Installation Complete!
echo ==============================================
echo.
echo Next steps:
echo 1. Quit Claude Desktop completely
echo 2. Reopen Claude Desktop
echo 3. Try asking: "What were the NBA scores last night?"
echo.
echo Features you can now use:
echo * Live NBA scores
echo * Player stats and game logs
echo * Team advanced analytics
echo * Box scores and play-by-play
echo.
pause
