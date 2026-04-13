@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    py -m venv .venv 2>nul || python -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo Instalando / actualizando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo Abriendo Market Signal App...
python -m streamlit run app.py

endlocal
