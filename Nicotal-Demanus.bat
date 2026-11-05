@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv" (
  echo Chua co moi truong, chay install.bat...
  call "%~dp0install.bat"
  if errorlevel 1 exit /b 1
)

if exist ".git" (
  call "%~dp0update.bat"
  if errorlevel 1 (
    echo [CANH BAO] Cap nhat that bai, tiep tuc voi phien ban hien tai.
  )
)

echo Khoi dong Demanus...
uv run demanus.py serve
if errorlevel 1 (
  echo [LOI] Server dung voi ma loi.
  pause
)
exit /b 0
