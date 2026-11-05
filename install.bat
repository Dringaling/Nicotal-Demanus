@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo Khong tim thay uv.
  where winget >nul 2>nul
  if not errorlevel 1 (
    choice /C YN /M "Cai uv bang winget"
    if not errorlevel 2 (
      winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
    )
  )
)

where uv >nul 2>nul
if errorlevel 1 (
  echo [LOI] Chua co uv.
  echo Cai thu cong: https://docs.astral.sh/uv/
  pause
  exit /b 1
)

if not exist ".venv" (
  echo Tao moi truong Python 3.12...
  uv venv .venv --python 3.12
  if errorlevel 1 (
    echo [LOI] Tao .venv that bai.
    pause
    exit /b 1
  )
) else (
  echo .venv da ton tai.
)

echo Cai dependencies...
uv sync
if errorlevel 1 (
  echo [LOI] uv sync that bai.
  pause
  exit /b 1
)

choice /C NY /M "Cai them preview Aspose (ton dung luong)"
if errorlevel 2 (
  echo Cai preview Aspose...
  uv sync --extra preview-aspose
  if errorlevel 1 (
    echo [CANH BAO] Cai preview Aspose that bai. Bo qua.
  )
)

echo Cai dat hoan tat.
choice /C YN /M "Chay phan mem ngay"
if errorlevel 2 exit /b 0
call "%~dp0Nicotal-Demanus.bat"
exit /b 0
