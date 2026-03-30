@echo off
chcp 65001 >nul

:: .env 파일 확인
if not exist ".env" (
    echo [오류] .env 파일이 없습니다. setup.bat 을 먼저 실행해주세요.
    pause
    exit /b 1
)

:: API 키 설정 확인
findstr /c:"여기에_텔레그램" .env >nul 2>&1
if not errorlevel 1 (
    echo [오류] .env 파일에 텔레그램 봇 토큰이 설정되지 않았습니다.
    echo 메모장으로 .env 파일을 열어 토큰을 입력해주세요.
    notepad .env
    pause
    exit /b 1
)

:: 이미 실행 중인 봇 종료
taskkill /f /im pythonw.exe >nul 2>&1

:: 백그라운드로 봇 실행
echo 봇을 백그라운드로 시작합니다...
start "" pythonw -m bot.main

timeout /t 2 >nul
echo.
echo ================================================
echo   랩미팅 봇이 실행되었습니다!
echo   텔레그램에서 봇을 검색해 /start 를 보내보세요.
echo   봇을 종료하려면 stop_bot.bat 을 실행하세요.
echo ================================================
echo.
pause
