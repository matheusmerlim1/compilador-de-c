"""Ponto de entrada do aplicativo (janela).

E este arquivo que vira o Compilador-de-C.exe. Aceita um arquivo .c como
argumento, para funcionar no "Abrir com" do Windows.
"""
import sys
import traceback
from pathlib import Path


def _pasta_base():
    """Pasta do programa, funcionando tanto solto quanto dentro do .exe."""
    if getattr(sys, "frozen", False):          # empacotado pelo PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main():
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, str(_pasta_base()))

    try:
        from ccrun.editor import abrir_editor
    except Exception:
        _mostrar_falha(traceback.format_exc())
        return 1

    alvo = None
    for arg in sys.argv[1:]:
        if arg.lower().endswith(".c") and Path(arg).is_file():
            alvo = arg
            break

    try:
        abrir_editor(alvo)
    except Exception:
        _mostrar_falha(traceback.format_exc())
        return 1
    return 0


def _mostrar_falha(detalhe):
    """Sem console, um erro passaria despercebido: grava e mostra em uma caixa."""
    try:
        (_pasta_base() / "erro.log").write_text(detalhe, encoding="utf-8")
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(
            "Compilador de C",
            "Nao consegui abrir o programa.\n\n"
            + detalhe.strip().splitlines()[-1]
            + "\n\nDetalhes gravados em erro.log")
        raiz.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
