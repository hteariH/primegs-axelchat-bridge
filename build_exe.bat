@echo off
chcp 866 >nul
cd /d "%~dp0"
echo === Сборка primegs_bridge.exe ===

python --version
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH. Установите Python с https://python.org
    echo          и при установке поставьте галочку "Add python.exe to PATH".
    pause
    exit /b 1
)

echo Устанавливаю PyInstaller (если еще не стоит)...
python -m pip install --upgrade pyinstaller || (echo [ОШИБКА] pip install не удался & pause & exit /b 1)

set ICON_ARG=
if exist primegs.ico set ICON_ARG=--icon primegs.ico

echo Собираю один файл...
python -m PyInstaller --onefile --console %ICON_ARG% --name primegs_bridge primegs_bridge.py || (echo [ОШИБКА] сборка не удалась & pause & exit /b 1)

echo.
echo === Готово ===
echo Готовый файл: dist\primegs_bridge.exe
echo Положите рядом с ним primegs_bridge.json (или запустите exe один раз - он создаст шаблон).
pause
