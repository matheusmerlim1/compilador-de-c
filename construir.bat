@echo off
rem Gera o Compilador-de-C.exe em dist\, para publicar no GitHub.
rem Precisa de: python -m pip install pyinstaller pillow
cd /d "%~dp0"

echo Gerando o icone...
python recursos\gerar_icone.py
if errorlevel 1 goto erro

echo.
echo Empacotando o executavel...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "Compilador-de-C" ^
  --icon "recursos/compilador.ico" ^
  --add-data "ccrun/sem_buffer.c;ccrun" ^
  --hidden-import tkinter ^
  app.py
if errorlevel 1 goto erro

echo.
echo Pronto: dist\Compilador-de-C.exe
goto fim

:erro
echo.
echo A geracao falhou. Confira as mensagens acima.

:fim
pause
