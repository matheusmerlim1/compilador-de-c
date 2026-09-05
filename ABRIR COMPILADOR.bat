@echo off
rem Abre a janela do compilador de C. Pode dar duplo clique neste arquivo.
rem Se este arquivo nao abrir nada, use o "Abrir Compilador.pyw" ao lado,
rem ou o atalho "Compilador de C" na Area de Trabalho.
cd /d "%~dp0"

rem pythonw abre a janela sem deixar um terminal preto junto.
where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw "%~dp0cc.py" editor %*
    exit /b
)

rem Sem pythonw, tenta o python normal.
where python >nul 2>&1
if not errorlevel 1 (
    start "" python "%~dp0cc.py" editor %*
    exit /b
)

echo.
echo  ============================================================
echo   O Python nao foi encontrado neste computador.
echo.
echo   Baixe em https://www.python.org/downloads/
echo   e marque a caixa "Add Python to PATH" durante a instalacao.
echo  ============================================================
echo.
pause
