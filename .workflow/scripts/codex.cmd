@echo off
setlocal
set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..\..") do set PROJECT_ROOT=%%~fI
set MODEL_FILE=%PROJECT_ROOT%\.workflow\config\codex-model.txt
set CODEX_MODEL=
if exist "%MODEL_FILE%" (
  set /p CODEX_MODEL=<"%MODEL_FILE%"
)
if defined CODEX_MODEL (
  codex -m "%CODEX_MODEL%" %*
) else (
  codex %*
)
exit /b %ERRORLEVEL%
