@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PYTHON_CMD=python"
set "PATCHER_SCRIPT=shiny_patcher.py"
set "CONFIG_FILE=patcher_config.ini"

if not exist "%PATCHER_SCRIPT%" (
  echo [ERROR] Could not find "%PATCHER_SCRIPT%" in this folder.
  echo Put this .bat next to shiny_patcher.py.
  pause
  exit /b 1
)

if not exist "%CONFIG_FILE%" (
  >"%CONFIG_FILE%" (
    echo ; Gen 3 Shiny Odds Patcher config
    echo ; Set shiny odds as 1 in N ^(integer ^> 0^)
    echo odds=4096
  )
  echo [INFO] Created default config: "%CONFIG_FILE%"
)

if "%~1"=="" (
  echo Drag and drop one or more .gba ROM files onto this .bat file.
  echo Then edit "%CONFIG_FILE%" to change shiny odds.
  pause
  exit /b 1
)

call :load_odds
if errorlevel 1 (
  pause
  exit /b 1
)

echo [INFO] Using shiny odds: 1/!ODDS!
echo.

:process_next
if "%~1"=="" goto done
set "ROM_PATH=%~1"

if /I not "%~x1"==".gba" (
  echo [SKIP] "%ROM_PATH%" ^(not a .gba file^)
  shift
  goto process_next
)

if not exist "%ROM_PATH%" (
  echo [SKIP] "%ROM_PATH%" ^(file not found^)
  shift
  goto process_next
)

call :build_output_path "%ROM_PATH%"
echo [PATCH] "%ROM_PATH%"
echo [OUT]   "!OUTPUT_PATH!"
%PYTHON_CMD% "%PATCHER_SCRIPT%" "%ROM_PATH%" --odds !ODDS! --output "!OUTPUT_PATH!"
if errorlevel 1 (
  echo [FAIL] Patching failed for "%ROM_PATH%"
) else (
  echo [OK] Patched "%ROM_PATH%"
)
echo.

shift
goto process_next

:done
echo Finished.
pause
exit /b 0

:load_odds
set "ODDS="
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /I /B /C:"odds=" "%CONFIG_FILE%"`) do (
  if /I "%%~A"=="odds" set "ODDS=%%~B"
)

if not defined ODDS (
  echo [ERROR] Could not find odds=... in "%CONFIG_FILE%".
  exit /b 1
)

set "ODDS=!ODDS: =!"
echo(!ODDS!| findstr /R "^[1-9][0-9]*$" >nul
if errorlevel 1 (
  echo [ERROR] Invalid odds in "%CONFIG_FILE%": !ODDS!
  echo Use a positive integer, for example: odds=4096
  exit /b 1
)

exit /b 0

:build_output_path
set "BASE_DIR=%~dp1"
set "BASE_NAME=%~n1"
set "OUTPUT_PATH=%BASE_DIR%%BASE_NAME%.shiny_1in!ODDS!.gba"
if not exist "!OUTPUT_PATH!" exit /b 0

set /a IDX=2
:output_loop
set "OUTPUT_PATH=%BASE_DIR%%BASE_NAME%.shiny_1in!ODDS!_v!IDX!.gba"
if exist "!OUTPUT_PATH!" (
  set /a IDX+=1
  goto output_loop
)
exit /b 0
