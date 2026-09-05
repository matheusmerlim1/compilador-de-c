"""Abre a janela do compilador com duplo clique.

Arquivos .pyw sao abertos direto pelo pythonw.exe, sem passar pelo cmd.exe.
Serve como alternativa ao ABRIR COMPILADOR.bat quando o .bat nao funciona.
"""
import sys
import traceback
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

try:
    from ccrun.editor import abrir_editor

    abrir_editor(sys.argv[1] if len(sys.argv) > 1 else None)
except Exception:
    # Sem console para mostrar o erro: grava em arquivo e avisa numa caixa.
    detalhe = traceback.format_exc()
    try:
        (AQUI / "erro.log").write_text(detalhe, encoding="utf-8")
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(
            "Falha ao abrir o compilador",
            "Nao consegui abrir a janela.\n\n"
            + detalhe.strip().splitlines()[-1]
            + "\n\nDetalhes no arquivo erro.log, na pasta do programa.")
        raiz.destroy()
    except Exception:
        pass
