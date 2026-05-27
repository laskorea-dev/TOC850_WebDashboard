@echo off
:: Force CMD to use UTF-8 Encoding to prevent Korean character issues
chcp 65001 > nul

cd /d "%~dp0\dashboard"

echo ========================================================
echo [Dashboard] Starting web server, please wait...
echo             The web dashboard will open automatically!
echo ========================================================

:: Run React dev server in background
start /b npm run dev

:: Wait 3 seconds for boot
timeout /t 3 /nobreak > nul

:: Open web browser
start http://localhost:5173

echo ========================================================
echo [Dashboard] Dashboard opened in your browser successfully!
echo             You can close this command window now.
echo ========================================================
timeout /t 3 > nul
exit
