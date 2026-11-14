"""Card "O que mudou", mostrado uma vez depois de cada atualizacao.

Le novidades.json (gravado pelo atualizador) e separa os titulos dos commits pelo
padrao do githubGuia: `feat:` -> Novidades, `fix:` -> Correcoes. `chore:`, `docs:`,
`test:`, `style:` e `refactor:` nao interessam a quem usa e ficam de fora.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

_PREFIXO = re.compile(r"^(\w+)(\([^)]*\))?!?:\s*(.+)$")


def classificar(titulos: list[str]) -> tuple[list[str], list[str]]:
    novidades, correcoes = [], []
    for t in titulos:
        m = _PREFIXO.match(t.strip())
        if not m:
            continue
        tipo, texto = m.group(1).lower(), m.group(3).strip()
        texto = texto[:1].upper() + texto[1:]
        if tipo == "feat":
            novidades.append(texto)
        elif tipo == "fix":
            correcoes.append(texto)
    return novidades, correcoes


def pendentes(pasta: Path) -> dict | None:
    """Novidades ainda nao mostradas (e apaga o arquivo: o card aparece uma vez so)."""
    arq = Path(pasta) / "novidades.json"
    if not arq.exists():
        return None
    try:
        dados = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = None
    try:
        arq.unlink()
    except OSError:
        pass
    return dados


def com_aviso(funcao):
    """Roda funcao(progresso) fora da tela. So abre uma janelinha de espera se a
    funcao avisar progresso (download da versao nova): numa abertura comum, em que
    nao ha nada para baixar, nenhuma janela extra aparece."""
    estado = {"msg": None, "fim": None}

    def progresso(mensagem):
        estado["msg"] = mensagem

    def trabalho():
        estado["fim"] = funcao(progresso)

    t = threading.Thread(target=trabalho, daemon=True)
    t.start()
    while t.is_alive() and estado["msg"] is None:
        t.join(0.1)
    if t.is_alive():
        try:
            _janela_de_espera(t, estado)
        except Exception:
            pass
    t.join()
    return estado["fim"] or (False, "")


def _janela_de_espera(tarefa, estado):
    import tkinter as tk

    raiz = tk.Tk()
    raiz.title("Compilador de C")
    raiz.configure(bg="#ffffff")
    raiz.resizable(False, False)
    raiz.attributes("-topmost", True)
    rotulo = tk.Label(raiz, text=estado["msg"], bg="#ffffff", fg="#1c2230",
                      font=("Segoe UI", 11), padx=30, pady=22)
    rotulo.pack()
    tk.Label(raiz, text="O programa abre sozinho quando terminar.", bg="#ffffff",
             fg="#5b6474", font=("Segoe UI", 9), padx=30).pack(pady=(0, 18))
    raiz.update_idletasks()
    w, h = raiz.winfo_reqwidth(), raiz.winfo_reqheight()
    raiz.geometry("+%d+%d" % ((raiz.winfo_screenwidth() - w) // 2,
                              (raiz.winfo_screenheight() - h) // 3))

    def conferir():
        if tarefa.is_alive():
            rotulo.config(text=estado["msg"])
            raiz.after(150, conferir)
        else:
            raiz.destroy()

    raiz.after(150, conferir)
    raiz.mainloop()


def mostrar_card(dados: dict, fechar_sozinho_ms: int = 0) -> None:
    """Janela pequena e centralizada com o que foi atualizado e corrigido."""
    import tkinter as tk

    novidades, correcoes = classificar(dados.get("titulos", []))
    if not novidades and not correcoes:
        correcoes = ["Melhorias internas."]

    raiz = tk.Tk()
    raiz.title("Compilador de C atualizado")
    raiz.configure(bg="#ffffff")
    raiz.resizable(False, False)
    raiz.attributes("-topmost", True)
    f_titulo = ("Segoe UI", 15, "bold")
    f_secao = ("Segoe UI", 11, "bold")
    f_texto = ("Segoe UI", 10)

    quadro = tk.Frame(raiz, bg="#ffffff", padx=26, pady=22)
    quadro.pack(fill="both", expand=True)
    tk.Label(quadro, text="O Compilador de C foi atualizado", font=f_titulo,
             bg="#ffffff", fg="#1c2230").pack(anchor="w")
    versao = "versão %s  →  %s" % (dados.get("de") or "?", dados.get("para") or "?")
    tk.Label(quadro, text=versao, font=f_texto, bg="#ffffff",
             fg="#5b6474").pack(anchor="w", pady=(2, 12))

    for titulo, itens, cor in (("Novidades", novidades, "#1a7f37"),
                               ("Correções", correcoes, "#0b6bcb")):
        if not itens:
            continue
        tk.Label(quadro, text=titulo, font=f_secao, bg="#ffffff",
                 fg=cor).pack(anchor="w", pady=(6, 2))
        for item in itens[:12]:
            tk.Label(quadro, text="•  " + item, font=f_texto, bg="#ffffff", fg="#1c2230",
                     wraplength=460, justify="left").pack(anchor="w", padx=(6, 0))
        if len(itens) > 12:
            tk.Label(quadro, text="… e mais %d" % (len(itens) - 12), font=f_texto,
                     bg="#ffffff", fg="#5b6474").pack(anchor="w", padx=(6, 0))

    botao = tk.Button(quadro, text="OK, continuar", font=f_secao, bg="#0b6bcb",
                      fg="#ffffff", activebackground="#0a5db0",
                      activeforeground="#ffffff", relief="flat", padx=18, pady=6,
                      command=raiz.destroy)
    botao.pack(anchor="e", pady=(18, 0))
    botao.focus_set()
    raiz.bind("<Return>", lambda _: raiz.destroy())
    raiz.bind("<Escape>", lambda _: raiz.destroy())

    raiz.update_idletasks()
    w, h = raiz.winfo_reqwidth(), raiz.winfo_reqheight()
    raiz.geometry("+%d+%d" % ((raiz.winfo_screenwidth() - w) // 2,
                              (raiz.winfo_screenheight() - h) // 3))
    if fechar_sozinho_ms:
        raiz.after(fechar_sozinho_ms, raiz.destroy)
    raiz.mainloop()
