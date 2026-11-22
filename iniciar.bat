@echo off
setlocal
cd /d "%~dp0"

title Mineria Academica

:menu
cls
echo ================================================
echo            MINERIA ACADEMICA
echo ================================================
echo.
echo  1. Instalar dependencias
echo  2. Abrir menu de Python
echo  3. Ejecutar pipeline completo
echo  4. Iniciar aplicacion web local
echo  0. Salir
echo.
set /p opcion="Selecciona una opcion: "

if "%opcion%"=="1" goto instalar
if "%opcion%"=="2" goto consola
if "%opcion%"=="3" goto pipeline
if "%opcion%"=="4" goto web
if "%opcion%"=="0" goto salir
goto menu

:instalar
where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo.
        echo No se encontro Python. Instala Python 3.10 o superior.
        pause
        goto menu
    )
    set "PYTHON=python"
) else (
    set "PYTHON=py"
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Creando entorno virtual .venv ...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo Error al crear el entorno virtual.
        pause
        goto menu
    )
)

echo.
echo Instalando dependencias de Python...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

where npm >nul 2>nul
if not errorlevel 1 (
    if not exist "web\node_modules" (
        echo.
        echo Instalando dependencias de la aplicacion web...
        cd /d "%~dp0web"
        call npm install
        cd /d "%~dp0"
    )
)

echo.
echo Instalacion completada.
pause
goto menu

:consola
call :preparar_python
if errorlevel 1 goto menu
".venv\Scripts\python.exe" main.py
echo.
pause
goto menu

:pipeline
call :preparar_python
if errorlevel 1 goto menu
".venv\Scripts\python.exe" main.py --todo
echo.
pause
goto menu

:web
call :preparar_python
if errorlevel 1 goto menu

where npm >nul 2>nul
if errorlevel 1 (
    echo.
    echo No se encontro npm. Instala Node.js para usar la interfaz web.
    pause
    goto menu
)

if not exist "web\node_modules" (
    echo.
    echo Instalando dependencias de la interfaz web...
    cd /d "%~dp0web"
    call npm install
    cd /d "%~dp0"
    if errorlevel 1 (
        echo Error al instalar las dependencias web.
        pause
        goto menu
    )
)

echo.
echo Iniciando API en http://127.0.0.1:8000
start "Mineria Academica - API" cmd /k ""%~dp0.venv\Scripts\python.exe" -m uvicorn backend.api:app --host 127.0.0.1 --port 8000"

echo Iniciando interfaz web...
start "Mineria Academica - Web" /d "%~dp0web" cmd /k "npm run dev"

timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"
goto menu

:preparar_python
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo No existe el entorno virtual. Ejecuta primero la opcion 1.
    pause
    exit /b 1
)
exit /b 0

:salir
endlocal
