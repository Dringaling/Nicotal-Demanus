@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

set "BRANCH=main"

where git >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong tim thay git.
  echo Cai Git for Windows: https://git-scm.com/download/win
  pause
  exit /b 1
)

if not exist ".git" (
  echo [LOI] Khong tim thay .git trong %CD%.
  echo Hay clone repo truoc khi chay update.
  pause
  exit /b 1
)

echo Dang kiem tra cap nhat...
git fetch --depth=1 origin %BRANCH% >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong fetch duoc tu remote.
  pause
  exit /b 1
)

for /f "delims=" %%A in ('git rev-parse HEAD') do set "LOCAL=%%A"
for /f "delims=" %%A in ('git rev-parse origin/%BRANCH%') do set "REMOTE=%%A"

if /I "%LOCAL%"=="%REMOTE%" (
  echo Da la phien ban moi nhat.
  exit /b 0
)

echo Co ban cap nhat moi.
echo CANH BAO: cap nhat se reset --hard va xoa thay doi cuc bo.
choice /C YN /M "Cap nhat ngay"
if errorlevel 2 exit /b 0

git reset --hard origin/%BRANCH%
if errorlevel 1 (
  echo [LOI] Cap nhat that bai.
  pause
  exit /b 1
)
echo Da cap nhat len %BRANCH%.
exit /b 0
