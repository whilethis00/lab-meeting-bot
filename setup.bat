@echo off
chcp 65001 >nul
echo.
echo ================================================
echo   랩미팅 봇 설치 중...
echo ================================================
echo.

:: Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo python.org 에서 Python 3.11 이상을 설치해주세요.
    echo.
    pause
    exit /b 1
)

echo [1/3] Python 패키지 설치 중...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [오류] 패키지 설치 실패. 인터넷 연결을 확인해주세요.
    pause
    exit /b 1
)

echo [2/3] 폴더 생성 중...
if not exist "data" mkdir data
if not exist "labmeeting" mkdir labmeeting

echo [3/3] 환경변수 파일 확인 중...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo ================================================
    echo   [필수] .env 파일을 열어서 API 키를 입력하세요!
    echo ================================================
    echo.
    echo   메모장으로 .env 파일을 열어드립니다...
    timeout /t 2 >nul
    notepad .env
) else (
    echo .env 파일이 이미 존재합니다.
)

echo.
echo ================================================
echo   설치 완료! start_bot.bat 을 실행하세요.
echo ================================================
echo.
pause
