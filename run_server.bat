@echo off
REM Run the AWS Amplify Documentation MCP Server on Windows

REM Get the directory where this script is located
set DIR=%~dp0

REM Change to the script directory
cd /d "%DIR%"

REM Check if uv is installed
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: uv is not installed. Please install uv first.
    echo Visit: https://github.com/astral-sh/uv
    exit /b 1
)

REM Run the server with uv
echo Starting AWS Amplify Documentation MCP Server...
uv run python amplify_docs_server.py