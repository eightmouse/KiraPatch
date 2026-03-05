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
    echo ; Set mode as one of: auto, native, reroll
    echo odds=256
    echo mode=auto
  )
  echo [INFO] Created default config: "%CONFIG_FILE%"
)

if "%~1"=="" (
  echo Drag and drop one or more .gba ROM files onto this .bat file.
  echo It reads odds and mode from "%CONFIG_FILE%".
  pause
  exit /b 1
)

call :load_config
if errorlevel 1 (
  pause
  exit /b 1
)

echo [INFO] Using shiny odds: 1/!ODDS!
echo [INFO] Using patch mode: !MODE!
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
%PYTHON_CMD% "%PATCHER_SCRIPT%" "%ROM_PATH%" --odds !ODDS! --mode !MODE! --output "!OUTPUT_PATH!"
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

:load_config
set "ODDS="
set "MODE="

for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /I /B /C:"odds=" /C:"mode=" "%CONFIG_FILE%"`) do (
  if /I "%%~A"=="odds" set "ODDS=%%~B"
  if /I "%%~A"=="mode" set "MODE=%%~B"
)

if not defined ODDS (
  echo [ERROR] Could not find odds=... in "%CONFIG_FILE%".
  exit /b 1
)

if not defined MODE (
  echo [ERROR] Could not find mode=... in "%CONFIG_FILE%".
  exit /b 1
)

set "ODDS=!ODDS: =!"
set "MODE=!MODE: =!"

echo(!ODDS!| findstr /R "^[1-9][0-9]*$" >nul
if errorlevel 1 (
  echo [ERROR] Invalid odds in "%CONFIG_FILE%": !ODDS!
  echo Use a positive integer, for example: odds=4096
  exit /b 1
)

if /I "!MODE!"=="auto" set "MODE=auto"
if /I "!MODE!"=="native" set "MODE=native"
if /I "!MODE!"=="reroll" set "MODE=reroll"

if /I not "!MODE!"=="auto" if /I not "!MODE!"=="native" if /I not "!MODE!"=="reroll" (
  echo [ERROR] Invalid mode in "%CONFIG_FILE%": !MODE!
  echo Use mode=auto, mode=native, or mode=reroll
  exit /b 1
)

exit /b 0

:build_output_path
set "BASE_DIR=%~dp1"
set "BASE_NAME=%~n1"
set "OUTPUT_PATH=%BASE_DIR%%BASE_NAME%.shiny_1in!ODDS!_!MODE!.gba"
if not exist "!OUTPUT_PATH!" exit /b 0

set /a IDX=2
:output_loop
set "OUTPUT_PATH=%BASE_DIR%%BASE_NAME%.shiny_1in!ODDS!_!MODE!_v!IDX!.gba"
if exist "!OUTPUT_PATH!" (
  set /a IDX+=1
  goto output_loop
)
exit /b 0
