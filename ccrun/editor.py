"""Janela para escrever, rodar e verificar codigo em C.

Reaproveita os mesmos modulos da linha de comando: quem compila, executa e
traduz os erros continua sendo o ccrun.
"""
import os
import queue
import subprocess
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from . import compilar as mod_compilar
from . import diagnosticos, executar, testes, toolchain

FUNDO = "#1e1e1e"
FUNDO_CLARO = "#252526"
TEXTO = "#d4d4d4"
LINHAS = "#6e7681"
SELECAO = "#264f78"
DESTAQUE_ERRO = "#5a1d1d"
VERDE = "#4ec9b0"
VERMELHO = "#f48771"
AMARELO = "#dcdcaa"
AZUL = "#569cd6"
CINZA = "#808080"
LARANJA = "#ce9178"

PALAVRAS_CHAVE = [
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "int",
    "long", "register", "return", "short", "signed", "sizeof", "static",
    "struct", "switch", "typedef", "union", "unsigned", "void", "volatile",
    "while", "bool", "true", "false", "NULL",
]

MODELO = """#include <stdio.h>

int main(void) {

    printf("Ola, mundo!\\n");

    return 0;
}
"""


class Editor(tk.Tk):
    def __init__(self, arquivo=None):
        super().__init__()
        self.title("Compilador de C")
        self.geometry("1100x740")
        self.configure(bg=FUNDO)
        self.minsize(760, 520)

        self.caminho = None          # arquivo .c aberto, se houver
        self.salvo = True
        self.compilador = toolchain.detectar()
        self.fila = queue.Queue()        # resultados da thread de compilacao
        self.fila_saida = queue.Queue()  # texto que o programa vai imprimindo
        self.rodando = False
        self.processo = None             # programa em execucao no console
        self.foi_parado = False
        self.terminal_automatico = False
        self.diags_atuais = []

        self.fonte = tkfont.Font(family="Consolas", size=12)
        self.fonte_ui = tkfont.Font(family="Segoe UI", size=9)

        self._montar()
        self._atalhos()

        if arquivo and Path(arquivo).is_file():
            self._abrir_caminho(Path(arquivo))
        else:
            self.codigo.insert("1.0", MODELO)
            self.codigo.mark_set("insert", "5.4")
        self._pintar()
        self._numerar()
        self.salvo = True
        self._atualizar_titulo()

        if self.compilador is None:
            self.after(300, self._avisar_sem_compilador)
        else:
            self._status("pronto — " + self.compilador.nome, VERDE)

        self.protocol("WM_DELETE_WINDOW", self._sair)
        self.after(80, self._checar_fila)
        self.after(50, self._trazer_para_frente)

    def _trazer_para_frente(self):
        """Aberta por duplo clique no .bat, a janela nasce atras das outras e
        parece que nada aconteceu. Isto a puxa para a frente uma unica vez."""
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
            self.codigo.focus_set()
            # solta o "sempre na frente" logo em seguida, senao ela fica presa
            # por cima de tudo enquanto o usuario trabalha
            self.after(400, lambda: self.attributes("-topmost", False))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # construcao da janela
    # ------------------------------------------------------------------

    def _montar(self):
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        # No tema clam o Notebook desenha bordas claras; iguala tudo ao fundo.
        estilo.configure("TNotebook", background=FUNDO, borderwidth=0,
                         bordercolor=FUNDO, lightcolor=FUNDO, darkcolor=FUNDO,
                         tabmargins=(0, 0, 0, 0))
        estilo.configure("TNotebook.Tab", background=FUNDO_CLARO, foreground=TEXTO,
                         padding=(14, 6), borderwidth=0, bordercolor=FUNDO,
                         lightcolor=FUNDO_CLARO, darkcolor=FUNDO_CLARO)
        estilo.map("TNotebook.Tab",
                   background=[("selected", FUNDO_CLARO)],
                   foreground=[("selected", VERDE)],
                   lightcolor=[("selected", FUNDO_CLARO)],
                   expand=[("selected", (0, 0, 0, 0))])

        self._montar_barra()

        # A barra de status precisa ser empacotada ANTES do painel que expande,
        # senao o painel toma toda a altura e ela some.
        self._montar_status()

        painel = tk.PanedWindow(self, orient=tk.VERTICAL, bg=FUNDO,
                                sashwidth=6, sashrelief=tk.FLAT, bd=0)
        painel.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        painel.add(self._montar_editor(painel), minsize=200, stretch="always")
        painel.add(self._montar_paineis(painel), minsize=170, stretch="always")

    def _montar_barra(self):
        barra = tk.Frame(self, bg=FUNDO, height=44)
        barra.pack(fill=tk.X, padx=8, pady=(8, 6))

        def botao(texto, comando, cor=TEXTO, destaque=False):
            b = tk.Button(
                barra, text=texto, command=comando,
                bg="#0e639c" if destaque else FUNDO_CLARO,
                fg="white" if destaque else cor,
                activebackground="#1177bb" if destaque else "#333337",
                activeforeground="white",
                relief=tk.FLAT, bd=0, padx=14, pady=7,
                font=tkfont.Font(family="Segoe UI", size=9,
                                 weight="bold" if destaque else "normal"),
                cursor="hand2",
            )
            b.pack(side=tk.LEFT, padx=(0, 6))
            return b

        self.btn_rodar = botao("▶  Rodar   (F5)", self.rodar, destaque=True)
        self.btn_parar = botao("■  Parar   (Esc)", self.parar, cor=VERMELHO)
        self.btn_parar.config(state=tk.DISABLED)
        botao("Terminal   (Shift+F5)", self.rodar_terminal)
        botao("Verificar   (F7)", self.verificar)
        self.btn_testar = botao("Testar   (F6)", self.testar)
        tk.Frame(barra, bg="#3c3c3c", width=1, height=26).pack(
            side=tk.LEFT, padx=8, pady=4)
        botao("Novo", self.novo)
        botao("Abrir", self.abrir)
        botao("Salvar   (Ctrl+S)", self.salvar)

        self.rotulo_arquivo = tk.Label(barra, text="", bg=FUNDO, fg=CINZA,
                                       font=self.fonte_ui)
        self.rotulo_arquivo.pack(side=tk.RIGHT, padx=6)

    def _montar_editor(self, pai):
        quadro = tk.Frame(pai, bg=FUNDO)

        self.numeros = tk.Text(
            quadro, width=5, padx=8, pady=8, bg=FUNDO, fg=LINHAS,
            bd=0, highlightthickness=0, font=self.fonte, state=tk.DISABLED,
            takefocus=0, cursor="arrow",
        )
        self.numeros.pack(side=tk.LEFT, fill=tk.Y)

        rolagem = tk.Scrollbar(quadro, bd=0, bg=FUNDO_CLARO,
                               troughcolor=FUNDO, activebackground="#4f4f4f")
        rolagem.pack(side=tk.RIGHT, fill=tk.Y)

        self.codigo = tk.Text(
            quadro, bg=FUNDO, fg=TEXTO, insertbackground="#aeafad",
            selectbackground=SELECAO, bd=0, highlightthickness=0,
            font=self.fonte, wrap=tk.NONE, undo=True, maxundo=-1,
            padx=8, pady=8, tabs=self.fonte.measure("    "),
        )
        self.codigo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def rolar(*args):
            self.codigo.yview(*args)
            self.numeros.yview(*args)

        rolagem.config(command=rolar)

        def ao_rolar(inicio, fim):
            rolagem.set(inicio, fim)
            self.numeros.yview_moveto(inicio)

        self.codigo.config(yscrollcommand=ao_rolar)

        for tag, cor in (("chave", AZUL), ("texto", LARANJA),
                         ("comentario", "#6a9955"), ("preproc", "#c586c0"),
                         ("numero", "#b5cea8")):
            self.codigo.tag_configure(tag, foreground=cor)
        self.codigo.tag_configure("linha_erro", background=DESTAQUE_ERRO)

        self.codigo.bind("<KeyRelease>", self._ao_digitar)
        self.codigo.bind("<ButtonRelease-1>", lambda e: self._posicao())
        self.codigo.bind("<MouseWheel>", self._ao_rolar_mouse)
        self.codigo.bind("<Return>", self._ao_enter)
        self.codigo.bind("<Tab>", self._ao_tab)
        return quadro

    def _montar_paineis(self, pai):
        self.abas = ttk.Notebook(pai)

        def area(pai_, altura=8):
            t = tk.Text(pai_, bg=FUNDO_CLARO, fg=TEXTO, bd=0,
                        highlightthickness=0, font=self.fonte, wrap=tk.WORD,
                        height=altura, padx=10, pady=8, state=tk.DISABLED,
                        selectbackground=SELECAO)
            return t

        # --- aba Saida: entrada do programa + o que ele imprimiu
        aba_saida = tk.Frame(self.abas, bg=FUNDO_CLARO)
        tk.Label(aba_saida, text="  Entrada opcional — respostas prontas, uma por linha "
                          "(normalmente basta digitar direto no console abaixo)",
                 bg=FUNDO_CLARO, fg=CINZA, font=self.fonte_ui,
                 anchor="w").pack(fill=tk.X, pady=(6, 2))
        self.entrada = tk.Text(aba_saida, bg="#2d2d30", fg=TEXTO, bd=0,
                               highlightthickness=0, font=self.fonte, height=3,
                               padx=10, pady=6, insertbackground="#aeafad",
                               selectbackground=SELECAO)
        self.entrada.pack(fill=tk.X, padx=8)
        self.saida = area(aba_saida)
        self.saida.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        for tag, cor in (("ok", VERDE), ("erro", VERMELHO),
                         ("aviso", AMARELO), ("fraco", CINZA),
                         ("programa", TEXTO), ("digitado", "#9cdcfe")):
            self.saida.tag_configure(tag, foreground=cor)
        # o painel vira console durante a execucao: Enter manda a linha ao programa
        self.saida.bind("<Return>", self._console_enter)
        self.saida.bind("<Key>", self._console_tecla)
        self.saida.config(insertbackground="#aeafad")
        self.abas.add(aba_saida, text="Saída")

        # --- aba Erros: diagnosticos traduzidos, clicaveis
        aba_erros = tk.Frame(self.abas, bg=FUNDO_CLARO)
        self.erros = area(aba_erros, altura=10)
        self.erros.pack(fill=tk.BOTH, expand=True)
        for tag, cor in (("erro", VERMELHO), ("aviso", AMARELO),
                         ("dica", VERDE), ("fraco", CINZA), ("codigo", TEXTO)):
            self.erros.tag_configure(tag, foreground=cor)
        self.erros.tag_configure("clicavel", underline=True)
        self.abas.add(aba_erros, text="Erros")

        # --- aba Testes
        aba_testes = tk.Frame(self.abas, bg=FUNDO_CLARO)
        self.testes_txt = area(aba_testes, altura=10)
        self.testes_txt.pack(fill=tk.BOTH, expand=True)
        for tag, cor in (("ok", VERDE), ("erro", VERMELHO),
                         ("fraco", CINZA), ("aviso", AMARELO)):
            self.testes_txt.tag_configure(tag, foreground=cor)
        self.abas.add(aba_testes, text="Testes")

        self.abas.pack(fill=tk.BOTH, expand=True)
        return self.abas

    def _montar_status(self):
        barra = tk.Frame(self, bg="#007acc", height=24)
        barra.pack(fill=tk.X, side=tk.BOTTOM)
        barra.pack_propagate(False)
        self.rotulo_status = tk.Label(barra, text="", bg="#007acc", fg="white",
                                      font=self.fonte_ui, anchor="w", padx=10)
        self.rotulo_status.pack(side=tk.LEFT)
        self.rotulo_pos = tk.Label(barra, text="linha 1, coluna 1", bg="#007acc",
                                   fg="white", font=self.fonte_ui, padx=10)
        self.rotulo_pos.pack(side=tk.RIGHT)

    def _atalhos(self):
        self.bind("<F5>", lambda e: self.rodar())
        self.bind("<Shift-F5>", lambda e: self.rodar_terminal())
        self.bind("<Escape>", lambda e: self.parar())
        self.bind("<F6>", lambda e: self.testar())
        self.bind("<F7>", lambda e: self.verificar())
        self.bind("<Control-s>", lambda e: (self.salvar(), "break")[1])
        self.bind("<Control-o>", lambda e: (self.abrir(), "break")[1])
        self.bind("<Control-n>", lambda e: (self.novo(), "break")[1])

    # ------------------------------------------------------------------
    # comportamento do editor
    # ------------------------------------------------------------------

    def _ao_digitar(self, evento=None):
        if evento and evento.keysym in ("Up", "Down", "Left", "Right",
                                        "Home", "End", "Prior", "Next"):
            self._posicao()
            return
        self.salvo = False
        self._atualizar_titulo()
        self._numerar()
        self._pintar()
        self._posicao()
        self.codigo.tag_remove("linha_erro", "1.0", tk.END)

    def _ao_rolar_mouse(self, evento):
        self.numeros.yview_scroll(int(-evento.delta / 120), "units")

    def _ao_enter(self, evento):
        """Enter mantendo a indentacao da linha atual, e um nivel a mais depois de {."""
        linha = self.codigo.get("insert linestart", "insert")
        recuo = len(linha) - len(linha.lstrip(" "))
        if linha.rstrip().endswith("{"):
            recuo += 4
        self.codigo.insert("insert", "\n" + " " * recuo)
        self.codigo.see("insert")
        self._ao_digitar()
        return "break"

    def _ao_tab(self, evento):
        self.codigo.insert("insert", "    ")
        return "break"

    def _numerar(self):
        total = int(self.codigo.index("end-1c").split(".")[0])
        self.numeros.config(state=tk.NORMAL)
        self.numeros.delete("1.0", tk.END)
        self.numeros.insert("1.0", "\n".join(str(n) for n in range(1, total + 1)))
        self.numeros.tag_configure("dir", justify="right")
        self.numeros.tag_add("dir", "1.0", tk.END)
        self.numeros.config(state=tk.DISABLED)
        self.numeros.yview_moveto(self.codigo.yview()[0])

    def _pintar(self):
        """Coloracao simples: comentarios, textos, diretivas, palavras-chave."""
        import re

        conteudo = self.codigo.get("1.0", tk.END)
        for tag in ("chave", "texto", "comentario", "preproc", "numero"):
            self.codigo.tag_remove(tag, "1.0", tk.END)

        def marcar(padrao, tag, sinalizadores=0):
            for m in re.finditer(padrao, conteudo, sinalizadores):
                ini = "1.0+%dc" % m.start()
                fim = "1.0+%dc" % m.end()
                self.codigo.tag_add(tag, ini, fim)

        marcar(r"\b\d+\.?\d*\b", "numero")
        marcar(r"\b(" + "|".join(PALAVRAS_CHAVE) + r")\b", "chave")
        marcar(r"^[ \t]*#[a-z]+", "preproc", re.MULTILINE)
        marcar(r"\"(\\.|[^\"\\\n])*\"|'(\\.|[^'\\\n])*'", "texto")
        marcar(r"//[^\n]*|/\*.*?\*/", "comentario", re.DOTALL)

    def _posicao(self):
        linha, coluna = self.codigo.index("insert").split(".")
        self.rotulo_pos.config(text="linha %s, coluna %d" % (linha, int(coluna) + 1))

    def _atualizar_titulo(self):
        nome = self.caminho.name if self.caminho else "sem título"
        marca = "" if self.salvo else " •"
        self.title("Compilador de C — " + nome + marca)
        self.rotulo_arquivo.config(
            text=(str(self.caminho.parent) if self.caminho else "não salvo") + marca)

    def _status(self, texto, cor=None):
        self.rotulo_status.config(text=texto)
        fundo = {VERDE: "#0e7c5a", VERMELHO: "#a1260d", AMARELO: "#9a6700"}.get(cor, "#007acc")
        # a barra inteira muda de cor junto, inclusive o indicador de posicao
        self.rotulo_status.master.config(bg=fundo)
        self.rotulo_status.config(bg=fundo)
        self.rotulo_pos.config(bg=fundo)

    # ------------------------------------------------------------------
    # escrita nos paineis
    # ------------------------------------------------------------------

    def _escrever(self, area, partes, limpar=True):
        area.config(state=tk.NORMAL)
        if limpar:
            area.delete("1.0", tk.END)
        for texto, *tag in partes:
            area.insert(tk.END, texto, tag[0] if tag else ())
        area.config(state=tk.DISABLED)
        area.see("1.0")

    # ------------------------------------------------------------------
    # arquivos
    # ------------------------------------------------------------------

    def novo(self):
        if not self._confirmar_descarte():
            return
        self.codigo.delete("1.0", tk.END)
        self.codigo.insert("1.0", MODELO)
        self.codigo.mark_set("insert", "5.4")
        self.caminho = None
        self.salvo = True
        self._pintar()
        self._numerar()
        self._atualizar_titulo()
        self._escrever(self.saida, [])
        self._escrever(self.erros, [])
        self._status("arquivo novo")

    def abrir(self):
        if not self._confirmar_descarte():
            return
        escolha = filedialog.askopenfilename(
            title="Abrir arquivo em C",
            filetypes=[("Arquivos em C", "*.c"), ("Todos", "*.*")],
            initialdir=str(self.caminho.parent) if self.caminho else str(Path.cwd()),
        )
        if escolha:
            self._abrir_caminho(Path(escolha))

    def _abrir_caminho(self, caminho):
        try:
            conteudo = caminho.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            messagebox.showerror("Erro ao abrir", str(e))
            return
        self.codigo.delete("1.0", tk.END)
        self.codigo.insert("1.0", conteudo)
        self.caminho = caminho
        self.salvo = True
        self._pintar()
        self._numerar()
        self._atualizar_titulo()
        self._status("aberto: " + caminho.name)

    def salvar(self):
        if self.caminho is None:
            escolha = filedialog.asksaveasfilename(
                title="Salvar como", defaultextension=".c",
                filetypes=[("Arquivos em C", "*.c")],
                initialfile="exercicio.c",
            )
            if not escolha:
                return False
            self.caminho = Path(escolha)
        try:
            self.caminho.write_text(self.codigo.get("1.0", "end-1c"), encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Erro ao salvar", str(e))
            return False
        self.salvo = True
        self._atualizar_titulo()
        self._status("salvo: " + self.caminho.name, VERDE)
        return True

    def _confirmar_descarte(self):
        if self.salvo:
            return True
        r = messagebox.askyesnocancel(
            "Alterações não salvas",
            "Você mexeu no código e ainda não salvou.\n\nSalvar antes de continuar?")
        if r is None:
            return False
        if r:
            return self.salvar()
        return True

    def _sair(self):
        if self.processo is not None:
            if not messagebox.askyesno(
                    "Programa rodando",
                    "Ainda há um programa em execução.\n\nParar e fechar mesmo assim?"):
                return
            self.parar()
        if self._confirmar_descarte():
            self.destroy()

    # ------------------------------------------------------------------
    # compilar / executar
    # ------------------------------------------------------------------

    def _avisar_sem_compilador(self):
        self._status("nenhum compilador C encontrado", VERMELHO)
        self._escrever(self.erros, [
            ("Nenhum compilador C encontrado nesta máquina.\n\n", "erro"),
            (toolchain.INSTRUCOES_INSTALACAO, "fraco"),
        ])
        self.abas.select(1)

    def _fonte_para_compilar(self):
        """Devolve o .c a compilar. Sem arquivo salvo, usa uma copia temporaria."""
        if self.caminho is not None:
            if not self.salvo and not self.salvar():
                return None
            return self.caminho
        pasta = Path(tempfile.gettempdir()) / "compilador_de_c"
        pasta.mkdir(parents=True, exist_ok=True)
        alvo = pasta / "sem_nome.c"
        alvo.write_text(self.codigo.get("1.0", "end-1c"), encoding="utf-8")
        return alvo

    def _preparar(self):
        if self.compilador is None:
            self._avisar_sem_compilador()
            return None
        if self.rodando:
            return None
        return self._fonte_para_compilar()

    # ------------------------------------------------------------------
    # console interativo: o programa roda e conversa dentro da aba Saida
    # ------------------------------------------------------------------

    def _lancar_interativo(self, executavel, cwd, entrada_pronta=""):
        """Poe o programa para rodar conversando com o painel de saida."""
        try:
            self.processo = subprocess.Popen(
                [str(executavel)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,          # erros junto, na ordem certa
                text=True, encoding="utf-8", errors="replace",
                bufsize=0, cwd=str(cwd),
            )
        except OSError as e:
            self._escrever(self.saida, [("Nao consegui executar: " + str(e), "erro")])
            return

        self.rodando = True
        self.inicio_execucao = time.perf_counter()
        self.btn_rodar.config(state=tk.DISABLED)
        self.btn_parar.config(state=tk.NORMAL)

        self._escrever(self.saida, [])
        self.saida.config(state=tk.NORMAL)
        self.saida.mark_set("limite", "end-1c")
        self.saida.mark_gravity("limite", tk.LEFT)
        self.saida.focus_set()
        self._status("rodando — digite as respostas aqui embaixo", VERDE)
        self.abas.select(0)

        threading.Thread(target=self._ler_saida_viva, daemon=True).start()

        if entrada_pronta.strip():
            for linha in entrada_pronta.splitlines():
                self._enviar_linha(linha, ecoar=True)

    def _ler_saida_viva(self):
        """Le a saida do programa em pedacos e entrega para a interface."""
        p = self.processo
        try:
            while True:
                pedaco = p.stdout.read(1)
                if not pedaco:
                    break
                self.fila_saida.put(pedaco)
        except (OSError, ValueError):
            pass
        finally:
            p.wait()
            self.fila_saida.put(("__fim__", p.returncode))

    def _bombear_saida(self):
        """Passa para a tela o que chegou do programa desde o ultimo giro."""
        acumulado = []
        terminou = None
        try:
            while True:
                item = self.fila_saida.get_nowait()
                if isinstance(item, tuple):
                    terminou = item[1]
                    break
                acumulado.append(item)
        except queue.Empty:
            pass

        if acumulado:
            self.saida.config(state=tk.NORMAL)
            self.saida.insert("end", "".join(acumulado), "programa")
            self.saida.mark_set("limite", "end-1c")
            self.saida.see("end")

        if terminou is not None:
            self._encerrar_interativo(terminou)

    def _encerrar_interativo(self, codigo):
        decorrido = time.perf_counter() - getattr(self, "inicio_execucao",
                                                  time.perf_counter())
        self.rodando = False
        self.processo = None
        self.btn_rodar.config(state=tk.NORMAL)
        self.btn_parar.config(state=tk.DISABLED)

        self.saida.config(state=tk.NORMAL)
        if not self.saida.get("1.0", "end-1c").endswith("\n"):
            self.saida.insert("end", "\n")

        if getattr(self, "foi_parado", False):
            self.saida.insert("end", "\n■ interrompido por você\n", "aviso")
            self._status("interrompido", AMARELO)
        elif codigo == 0:
            self.saida.insert("end",
                              "\n✓ o programa terminou normalmente (%.2fs)\n" % decorrido, "ok")
            self._status("terminou sem erros (%.2fs)" % decorrido, VERDE)
        else:
            motivo, dica = executar.explicar_codigo(codigo)
            self.saida.insert("end", "\n✗ " + (motivo or "terminou com erro") + "\n", "erro")
            if dica:
                self.saida.insert("end", dica + "\n", "aviso")
            self._status(motivo or "terminou com erro", VERMELHO)

        self.foi_parado = False
        self.saida.see("end")
        self.saida.config(state=tk.DISABLED)

    def _enviar_linha(self, texto, ecoar=False):
        if not self.processo:
            return
        if ecoar:
            self.saida.config(state=tk.NORMAL)
            self.saida.insert("end", texto + "\n", "digitado")
            self.saida.mark_set("limite", "end-1c")
            self.saida.see("end")
        try:
            self.processo.stdin.write(texto + "\n")
            self.processo.stdin.flush()
        except (OSError, ValueError):
            pass  # o programa ja fechou a entrada

    def _console_enter(self, evento):
        if not self.rodando:
            return "break"
        digitado = self.saida.get("limite", "end-1c")
        self.saida.insert("end", "\n")
        self.saida.mark_set("limite", "end-1c")
        self.saida.see("end")
        self._enviar_linha(digitado)
        return "break"

    def _console_tecla(self, evento):
        """Deixa escrever so no fim: a saida ja impressa nao pode ser alterada."""
        if not self.rodando:
            return "break"
        if evento.keysym in ("Up", "Down", "Left", "Right", "Home", "End",
                             "Prior", "Next", "Control_L", "Control_R", "Shift_L",
                             "Shift_R", "Alt_L", "Alt_R"):
            return None
        if evento.state & 0x4 and evento.keysym.lower() in ("c", "a"):
            return None  # Ctrl+C / Ctrl+A continuam funcionando
        if self.saida.compare("insert", "<", "limite"):
            self.saida.mark_set("insert", "end")
        if evento.keysym == "BackSpace" and self.saida.compare("insert", "<=", "limite"):
            return "break"
        return None

    def parar(self):
        """Mata o programa que estiver rodando."""
        if not self.processo:
            return
        self.foi_parado = True
        try:
            self.processo.kill()
        except OSError:
            pass

    def _le_do_teclado(self):
        """O codigo pede dados a quem esta usando?"""
        import re

        codigo = self.codigo.get("1.0", "end-1c")
        codigo = re.sub(r"//[^\n]*|/\*.*?\*/", "", codigo, flags=re.DOTALL)
        return re.search(r"\b(scanf|getchar|gets|fgets|getline)\s*\(", codigo) is not None

    def rodar(self):
        """Roda no console da propria janela: o programa pergunta, voce responde."""
        fonte = self._preparar()
        if fonte is None:
            return
        self.terminal_automatico = False
        self._iniciar("interativo", fonte, self.entrada.get("1.0", "end-1c"))

    def rodar_terminal(self):
        """Executa numa janela de terminal de verdade, para programas que
        conversam com o usuario: as perguntas aparecem uma a uma e da para
        responder na hora, como no Code::Blocks."""
        fonte = self._preparar()
        if fonte is None:
            return
        self._iniciar("terminal", fonte, "")

    def _abrir_terminal(self, executavel, cwd):
        try:
            if os.name == "nt":
                # CREATE_NEW_CONSOLE (0x10) da uma janela de console propria ao
                # programa; o pause segura a janela aberta no fim.
                subprocess.Popen(
                    '"%s" & echo. & echo [o programa terminou] & pause' % executavel,
                    creationflags=0x00000010, cwd=str(cwd), shell=True)
            else:
                for term in ("x-terminal-emulator", "gnome-terminal", "xterm"):
                    try:
                        subprocess.Popen([term, "-e", str(executavel)], cwd=str(cwd))
                        break
                    except FileNotFoundError:
                        continue
            return True
        except Exception as e:
            self._escrever(self.saida, [
                ("Nao consegui abrir a janela de terminal.\n", "erro"), (str(e),)])
            return False

    def verificar(self):
        fonte = self._preparar()
        if fonte is None:
            return
        self._iniciar("verificar", fonte, "")

    def testar(self):
        fonte = self._preparar()
        if fonte is None:
            return
        casos, origem = testes.descobrir_casos(fonte)
        if not casos:
            self.abas.select(2)
            self._escrever(self.testes_txt, [
                ("Este exercício ainda não tem casos de teste.\n\n", "aviso"),
                ("Crie um arquivo chamado ", "fraco"),
                (fonte.stem + ".testes", "ok"),
                (" na mesma pasta, assim:\n\n", "fraco"),
                (testes.MODELO_ARQUIVO_TESTES, "fraco"),
            ])
            self._status("sem casos de teste", AMARELO)
            return
        self._iniciar("testar", fonte, "", casos=casos, origem=origem)

    def _iniciar(self, modo, fonte, entrada, casos=None, origem=None):
        self.rodando = True
        self.btn_rodar.config(state=tk.DISABLED)
        self.codigo.tag_remove("linha_erro", "1.0", tk.END)
        self._status("compilando...", None)
        self._escrever(self.saida, [("compilando...\n", "fraco")])
        t = threading.Thread(
            target=self._trabalhar,
            args=(modo, fonte, entrada, casos, origem),
            daemon=True)
        t.start()

    def _trabalhar(self, modo, fonte, entrada, casos, origem):
        """Roda fora da thread da interface para a janela nao congelar."""
        try:
            destino = mod_compilar.caminho_saida(fonte, fonte.parent / "build")
            comp = mod_compilar.compilar(
                self.compilador, [fonte], destino,
                # nos dois modos que conversam com o usuario, a saida precisa
                # sair sem buffer, senao as perguntas nao aparecem na hora
                interativo=modo in ("interativo", "terminal"))
            if not comp.sucesso or modo == "verificar":
                self.fila.put(("compilacao", modo, comp, fonte, None))
                return

            if modo == "interativo":
                self.fila.put(("interativo", modo, comp, fonte, (destino, entrada)))
                return

            if modo == "terminal":
                # so compila aqui; abrir a janela e trabalho da interface
                self.fila.put(("terminal", modo, comp, fonte, destino))
                return

            if modo == "rodar":
                res = executar.executar(destino, entrada=(entrada or "") + "\n",
                                        timeout=10, cwd=fonte.parent)
                self.fila.put(("execucao", modo, comp, fonte, res))
                return

            resultados = []
            for caso in casos:
                res = executar.executar(destino, entrada=caso.entrada + "\n",
                                        args=caso.args, timeout=10, cwd=fonte.parent)
                if res.expirou or res.codigo != 0:
                    resultados.append(testes.ResultadoTeste(
                        caso, False, res.saida, res.tempo,
                        falha=res.motivo, dica=res.dica))
                    continue
                igual, linha = testes.comparar(caso.esperado, res.saida)
                resultados.append(testes.ResultadoTeste(
                    caso, igual, res.saida, res.tempo, linha_erro=linha))
            self.fila.put(("testes", modo, comp, fonte, (resultados, origem)))
        except Exception as e:  # nunca deixa a thread morrer calada
            self.fila.put(("falha", modo, None, fonte, e))

    def _checar_fila(self):
        try:
            while True:
                item = self.fila.get_nowait()
                self._processar(item)
        except queue.Empty:
            pass
        self._bombear_saida()
        self.after(40, self._checar_fila)

    def _processar(self, item):
        tipo, modo, comp, fonte, extra = item
        self.rodando = False
        self.btn_rodar.config(state=tk.NORMAL)

        if tipo == "falha":
            self._status("erro interno", VERMELHO)
            self._escrever(self.erros, [("Erro inesperado:\n", "erro"), (str(extra),)])
            self.abas.select(1)
            return

        self._mostrar_diagnosticos(comp, fonte)

        if not comp.sucesso:
            erros, _ = diagnosticos.contar(comp.diags)
            self._status("não compilou — %d erro(s)" % max(erros, 1), VERMELHO)
            self.abas.select(1)
            return

        if tipo == "compilacao":  # modo verificar, compilou
            _, avisos = diagnosticos.contar(comp.diags)
            if avisos:
                self._status("compilou com %d aviso(s)" % avisos, AMARELO)
                self.abas.select(1)
            else:
                self._status("compilou sem nenhum erro", VERDE)
                self._escrever(self.erros, [("Nenhum erro. Código limpo.\n", "dica")])
                self.abas.select(1)
            return

        if tipo == "interativo":
            destino, entrada = extra
            self._lancar_interativo(destino, fonte.parent, entrada)
            return

        if tipo == "terminal":
            if self._abrir_terminal(extra, fonte.parent):
                partes = []
                if getattr(self, "terminal_automatico", False):
                    partes += [
                        ("Seu programa pede dados a quem está usando, e a caixa "
                         "Entrada está vazia.\n", "aviso"),
                        ("Por isso abri o programa em uma janela de terminal, onde "
                         "você digita na hora.\n\n", "aviso"),
                    ]
                else:
                    partes.append(
                        ("O programa abriu em uma janela de terminal separada.\n\n", "ok"))
                partes.append(
                    ("As perguntas aparecem uma a uma e você responde ali mesmo.\n"
                     "Quando o programa terminar, aperte uma tecla para fechar "
                     "aquela janela.\n\n", "fraco"))
                partes.append(
                    ("Se preferir que o resultado apareça aqui, escreva as respostas "
                     "na caixa Entrada acima (uma por linha) e aperte F5 de novo.\n",
                     "fraco"))
                self._escrever(self.saida, partes)
                self._status("rodando no terminal — responda na janela preta", VERDE)
                self.abas.select(0)
            return

        if tipo == "execucao":
            self._mostrar_execucao(extra)
            return

        if tipo == "testes":
            self._mostrar_testes(*extra)

    def _mostrar_diagnosticos(self, comp, fonte):
        if not comp.diags:
            self._escrever(self.erros, [("Nenhum erro nem aviso.\n", "dica")])
            return

        partes = []
        for d in comp.diags:
            eh_erro = d.e_erro
            tag = "erro" if eh_erro else "aviso"
            rotulo = "ERRO" if eh_erro else "AVISO"
            local = ("linha %d" % d.linha) if d.linha else "ligação"
            partes.append((rotulo + "  " + local + "\n", tag))
            partes.append(("   " + (d.traducao or d.mensagem) + "\n",))
            if d.traducao:
                partes.append(("   original: " + d.mensagem + "\n", "fraco"))
            if d.linha:
                trecho = self.codigo.get("%d.0" % d.linha, "%d.end" % d.linha)
                if trecho.strip():
                    partes.append(("   %d | %s\n" % (d.linha, trecho.strip()), "codigo"))
            if d.dica:
                partes.append(("   como corrigir: " + d.dica + "\n", "dica"))
            partes.append(("\n",))

        self._escrever(self.erros, partes)

        # pinta no editor as linhas com erro e leva o cursor para a primeira
        primeira = None
        for d in comp.diags:
            if d.linha:
                self.codigo.tag_add("linha_erro",
                                    "%d.0" % d.linha, "%d.end+1c" % d.linha)
                if primeira is None and d.e_erro:
                    primeira = d.linha
        if primeira:
            self.codigo.mark_set("insert", "%d.0" % primeira)
            self.codigo.see("%d.0" % primeira)

    # Um laco descontrolado gera megabytes de texto; jogar tudo dentro do
    # widget travaria a janela.
    LIMITE_MOSTRADO = 4000

    def _mostrar_execucao(self, res):
        partes = []
        if res.saida:
            texto = res.saida
            cortado = len(texto) - self.LIMITE_MOSTRADO
            if cortado > 0:
                texto = texto[:self.LIMITE_MOSTRADO]
            if not texto.endswith("\n"):
                texto += "\n"
            partes.append((texto,))
            if cortado > 0:
                partes.append(("\n[... mais %d caracteres não mostrados ...]\n"
                               % cortado, "fraco"))
        if res.erros.strip():
            partes.append(("\n[mensagens de erro do programa]\n", "aviso"))
            partes.append((res.erros,))

        if res.sucesso:
            partes.append(("\n✓ o programa terminou normalmente (%.3fs)\n" % res.tempo, "ok"))
            self._status("executou sem erros (%.3fs)" % res.tempo, VERDE)
        else:
            partes.append(("\n✗ " + (res.motivo or "o programa falhou") + "\n", "erro"))
            # Travou pedindo dados que ninguem forneceu: e o caso mais comum de
            # todos, e a dica generica de laco infinito nao ajuda em nada aqui.
            if res.expirou and self._le_do_teclado():
                partes.append((
                    "\nO seu programa continuou pedindo dados depois que as "
                    "respostas da caixa Entrada acabaram.\n\n", "aviso"))
                partes.append((
                    "Duas saídas:\n"
                    "  1. Aperte Shift+F5 para rodar em uma janela de terminal e "
                    "digitar as respostas na hora.\n"
                    "  2. Ou complete a caixa Entrada com TODAS as respostas, "
                    "inclusive a que faz o programa terminar.\n", "fraco"))
            elif res.dica:
                partes.append(("\nprovável causa:\n" + res.dica + "\n", "aviso"))
            self._status(res.motivo or "o programa falhou", VERMELHO)

        if not res.saida.strip() and res.sucesso:
            partes.append(("\n(o programa não imprimiu nada)\n", "fraco"))

        self._escrever(self.saida, partes)
        self.abas.select(0)

    def _mostrar_testes(self, resultados, origem):
        partes = [("%d caso(s) em %s\n\n" % (len(resultados), Path(origem).name), "fraco")]
        passaram = 0
        for r in resultados:
            if r.passou:
                passaram += 1
                partes.append(("✓ ", "ok"))
                partes.append((r.caso.nome, "ok"))
                partes.append(("   (%.3fs)\n" % r.tempo, "fraco"))
                continue

            partes.append(("✗ ", "erro"))
            partes.append((r.caso.nome + "\n", "erro"))
            if r.caso.entrada.strip():
                partes.append(("   entrada: " +
                               r.caso.entrada.strip().replace("\n", " | ") + "\n", "fraco"))
            if r.falha:
                partes.append(("   " + r.falha + "\n", "erro"))
                if r.dica:
                    partes.append(("   " + r.dica + "\n", "aviso"))
            else:
                esperado = r.caso.esperado.strip() or "(nada)"
                obtido = r.obtido.strip() or "(nada)"
                partes.append(("   esperado:\n", "fraco"))
                for l in esperado.splitlines():
                    partes.append(("      " + l + "\n", "ok"))
                partes.append(("   obtido:\n", "fraco"))
                for l in obtido.splitlines():
                    partes.append(("      " + l + "\n", "erro"))
            partes.append(("\n",))

        total = len(resultados)
        cabecalho = "%d de %d caso(s) passaram\n\n" % (passaram, total)
        partes.insert(0, (cabecalho, "ok" if passaram == total else "erro"))
        self._escrever(self.testes_txt, partes)
        self.abas.select(2)
        if passaram == total:
            self._status("todos os %d testes passaram" % total, VERDE)
        else:
            self._status("%d de %d testes passaram" % (passaram, total), VERMELHO)


def abrir_editor(arquivo=None):
    Editor(arquivo).mainloop()
