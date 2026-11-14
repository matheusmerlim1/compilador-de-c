"""Compilacao de um arquivo .c com flags rigorosas."""
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import diagnosticos

# Avisos ligados por padrao: pegam a maioria dos erros de logica de iniciante
# antes mesmo do programa rodar.
FLAGS_GCC = [
    "-std=c11",
    "-Wall",              # avisos essenciais
    "-Wextra",            # avisos adicionais
    "-Wshadow",           # variavel que esconde outra de fora
    "-Wformat=2",         # printf/scanf com formato errado
    "-Wuninitialized",
    "-Wno-unused-result",
    "-g",                 # simbolos de depuracao
    "-fdiagnostics-color=never",
]

FLAGS_MSVC = ["/W4", "/nologo", "/Zi", "/EHsc"]

# OpenMP: ligado sozinho quando o codigo usa, como o -fopenmp dos Makefiles da
# disciplina de Programacao Paralela. Sem ele o GCC ignora os #pragma omp
# calado (o programa roda com uma thread so) e omp_get_wtime nao liga.
_USA_OPENMP = re.compile(
    r"^[ \t]*#[ \t]*(?:pragma[ \t]+omp\b|include[ \t]*<omp\.h>)"
    r"|\bomp_[a-z_]+[ \t]*\(",
    re.MULTILINE)


def usa_openmp(fontes):
    """True se algum dos fontes tem #pragma omp, #include <omp.h> ou omp_*()."""
    for f in fontes:
        try:
            texto = Path(f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _USA_OPENMP.search(texto):
            return True
    return False


@dataclass
class ResultadoCompilacao:
    sucesso: bool
    executavel: Path = None
    diags: list = field(default_factory=list)
    saida_bruta: str = ""
    comando: list = field(default_factory=list)
    sanitizador_indisponivel: bool = False
    openmp: bool = False

    @property
    def erros(self):
        return diagnosticos.contar(self.diags)[0]

    @property
    def avisos(self):
        return diagnosticos.contar(self.diags)[1]


def montar_comando(compilador, fontes, destino, otimizar=False, sanitizar=False,
                   extras=None, base=None, openmp=False):
    # Usa o caminho relativo a pasta de trabalho: as mensagens do compilador ficam
    # curtas ("soma.c:7:5") em vez de mostrarem o caminho absoluto inteiro.
    fontes_str = []
    for f in fontes:
        try:
            fontes_str.append(str(Path(f).relative_to(base)) if base else str(f))
        except ValueError:
            fontes_str.append(str(f))
    if compilador.familia == "msvc":
        cmd = [compilador.caminho] + FLAGS_MSVC + (["/openmp"] if openmp else []) + fontes_str
        cmd += ["/Fe:" + str(destino)]
        return cmd + list(extras or [])

    cmd = [compilador.caminho] + FLAGS_GCC
    cmd += ["-O2"] if otimizar else ["-O0"]
    if sanitizar:
        # Detecta acesso invalido de memoria e overflow em tempo de execucao.
        cmd += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    cmd += fontes_str
    cmd += ["-o", str(destino)]
    cmd += ["-lm"]  # biblioteca matematica: sempre ligada, evita erro com sqrt/pow
    if openmp:
        cmd += ["-fopenmp"]
    return cmd + list(extras or [])


AUXILIAR = Path(__file__).resolve().parent / "apoio.c"

# Faz as chamadas de scanf do exercicio caírem no nosso __wrap_scanf, que
# confere se a leitura deu certo. Sem isto, digitar letra onde se espera
# numero não avisa nada.
LIGACAO_APOIO = ["-Wl,--wrap=scanf"]

# Declara no Windows funcoes POSIX dos exemplos de Programacao Paralela
# (rand_r). O corpo fica em apoio.c.
COMPAT_POSIX = Path(__file__).resolve().parent / "compat_posix.h"


def compilar(compilador, fontes, destino, otimizar=False, sanitizar=False,
             extras=None, timeout=90, apoio=True, openmp=None):
    """Compila e devolve o resultado ja com os diagnosticos analisados.

    Com apoio=True (o normal), junta o arquivo ccrun/apoio.c, que desliga o
    buffer da saida e avisa quando um scanf nao consegue ler o que pediu.

    openmp=None descobre sozinho pelo codigo; True/False força."""
    fontes = list(fontes)
    if openmp is None:
        openmp = usa_openmp(fontes)
    com_apoio = apoio and compilador.familia == "gcc" and AUXILIAR.is_file()
    if com_apoio:
        fontes = fontes + [AUXILIAR]
        extras = list(extras or []) + LIGACAO_APOIO
        if os.name == "nt" and COMPAT_POSIX.is_file():
            extras += ["-include", str(COMPAT_POSIX)]
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        try:
            destino.unlink()
        except OSError:
            pass

    base = Path(fontes[0]).parent
    cmd = montar_comando(compilador, fontes, destino, otimizar, sanitizar, extras,
                         base=base, openmp=openmp)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, cwd=str(base))
    except subprocess.TimeoutExpired:
        d = diagnosticos.Diagnostico(
            nivel="error",
            mensagem="a compilacao passou de %ds e foi interrompida" % timeout,
            traducao="A compilacao demorou tempo demais e foi cancelada.",
            dica="Isso costuma indicar recursao infinita em macros ou include ciclico.",
        )
        return ResultadoCompilacao(False, None, [d], "", cmd, openmp=openmp)
    except FileNotFoundError:
        d = diagnosticos.Diagnostico(
            nivel="error",
            mensagem="compilador nao encontrado: " + compilador.caminho,
            traducao="Nao consegui executar o compilador.",
            dica="Rode: python cc.py doutor",
        )
        return ResultadoCompilacao(False, None, [d], "", cmd, openmp=openmp)

    bruta = (proc.stdout or "") + (proc.stderr or "")

    # As bibliotecas do sanitizador nao vem na maioria dos GCC para Windows.
    # Se a compilacao falhou por causa delas, recompila sem e avisa depois.
    if sanitizar and proc.returncode != 0:
        marcas = ("sanitize", "-lasan", "-lubsan", "libasan", "libubsan")
        if any(m in bruta.lower() for m in marcas):
            res = compilar(compilador, fontes, destino, otimizar,
                           sanitizar=False, extras=extras, timeout=timeout,
                           apoio=False, openmp=openmp)
            res.sanitizador_indisponivel = True
            return res

    diags = diagnosticos.analisar_saida(bruta, compilador.familia)

    # Caso comum depois de rodar no terminal: a janela do programa ficou aberta,
    # o Windows mantem o .exe travado e o compilador nao consegue regrava-lo.
    marcas_travado = ("permission denied", "cannot open output file",
                      "text file busy", "being used by another process")
    if proc.returncode != 0 and any(m in bruta.lower() for m in marcas_travado):
        diags.append(diagnosticos.Diagnostico(
            nivel="error",
            mensagem="nao foi possivel gravar " + destino.name,
            traducao="O programa anterior ainda esta rodando e segurando o arquivo.",
            dica="Feche a janela preta (terminal) onde ele ficou aberto e rode de novo.",
        ))

    # Junta a nossa revisao do fonte: armadilhas que o compilador aceita calado.
    # O auxiliar interno fica de fora, e codigo nosso.
    for fonte in fontes:
        if Path(fonte) != AUXILIAR:
            diags.extend(diagnosticos.revisar_fonte(fonte))
    sucesso = proc.returncode == 0 and destino.exists()
    if openmp and proc.returncode != 0 and any(
            m in bruta.lower() for m in ("-lgomp", "libgomp", "omp.h: no such file")):
        diags.append(diagnosticos.Diagnostico(
            nivel="error",
            mensagem="OpenMP indisponivel neste compilador",
            traducao="O codigo usa OpenMP, mas este compilador nao veio com a "
                     "biblioteca dele (libgomp).",
            dica="Instale o GCC do WinLibs, que ja traz o OpenMP:\n"
                 "     winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT",
        ))

    sucesso = proc.returncode == 0 and destino.exists()
    return ResultadoCompilacao(sucesso, destino if sucesso else None, diags, bruta, cmd,
                               openmp=openmp)


def caminho_saida(fonte, pasta_build):
    """Onde o executavel de um .c deve ser gerado."""
    import os
    sufixo = ".exe" if os.name == "nt" else ""
    return pasta_build / (fonte.stem + sufixo)
