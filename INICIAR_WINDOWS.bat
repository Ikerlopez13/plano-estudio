@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Instala Python 3.12 o superior desde python.org y vuelve a abrir este archivo.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe app.py
pause
exit /b 0
:error
echo No se pudo iniciar. Comprueba la instalacion de Python y la conexion a Internet.
pause
exit /b 1
