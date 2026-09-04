@echo off
chcp 65001 >nul
cd /d %~dp0
echo [복구센터] 서버를 시작합니다...
python server.py
pause
