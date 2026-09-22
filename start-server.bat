@echo off
cd /d "%~dp0"

netstat -ano | findstr ":8011" | findstr "LISTENING" >nul && (
  echo.
  echo  Port 8011 is ALREADY IN USE by another program.
  echo  Close it first, or the phone may load the OTHER app.
  echo  ^(Windows python binds a busy port without complaining.^)
  echo.
  pause & exit /b
)

echo.
echo  cet6-vocab - local server on port 8011
echo.
echo  On the phone (same Wi-Fi), open one of these in the browser:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
  for /f "tokens=* delims= " %%b in ("%%a") do echo      http://%%b:8011
)
echo.
echo  Keep this window open while using the app. Ctrl+C stops it.
echo.
python -m http.server 8011
pause
