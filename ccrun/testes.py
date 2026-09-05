"""Casos de teste: leitura dos arquivos, comparacao de saida e relatorio de diferencas."""
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from . import cores

CABECALHO = re.compile(r"^\s*={2,}\s*(?P<tag>[A-Za-zÀ-ú]+)\s*(?P<rotulo>.*?)\s*=*\s*$")


@dataclass
class CasoTeste:
    nome: str
    entrada: str = ""
    esperado: str = ""
    args: list = field(default_factory=list)


@dataclass
class ResultadoTeste:
    caso: CasoTeste
    passou: bool
    obtido: str = ""
    tempo: float = 0.0
    falha: str = ""      # motivo quando nao foi diferenca de saida (travou, quebrou...)
    dica: str = ""
    linha_erro: int = 0  # primeira linha divergente (1-based); 0 = nenhuma


def _sem_acento(txt):
    return "".join(ch for ch in unicodedata.normalize("NFD", txt)
                   if unicodedata.category(ch) != "Mn").upper()


def ler_arquivo_testes(caminho):
    """Le o formato de arquivo unico:

        === ENTRADA
        5 3
        === SAIDA
        8
    """
    texto = Path(caminho).read_text(encoding="utf-8", errors="replace")
    casos = []
    atual = None
    secao = None
    buffer = []
    contador = 0

    def fechar():
        nonlocal buffer
        if atual is None or secao is None:
            buffer = []
            return
        conteudo = "\n".join(buffer)
        if secao == "ENTRADA":
            atual.entrada = conteudo
        elif secao == "SAIDA":
            atual.esperado = conteudo
        elif secao == "ARGS":
            atual.args = conteudo.split()
        buffer = []

    for linha in texto.splitlines():
        m = CABECALHO.match(linha)
        if m:
            tag = _sem_acento(m.group("tag"))
            if tag in ("ENTRADA", "IN", "STDIN"):
                fechar()
                contador += 1
                rotulo = m.group("rotulo").strip()
                atual = CasoTeste(nome=rotulo or ("caso %d" % contador))
                casos.append(atual)
                secao = "ENTRADA"
            elif tag in ("SAIDA", "OUT", "STDOUT", "ESPERADO"):
                fechar()
                secao = "SAIDA"
            elif tag in ("ARGS", "ARGUMENTOS"):
                fechar()
                secao = "ARGS"
            else:
                fechar()
                secao = None
            continue
        if secao is not None:
            buffer.append(linha)
    fechar()
    return [c for c in casos if c.esperado or c.entrada]


def ler_pasta_testes(pasta):
    """Le o formato de pasta: 01.in + 01.out (o .out pode faltar)."""
    casos = []
    for entrada in sorted(Path(pasta).glob("*.in")):
        saida = entrada.with_suffix(".out")
        casos.append(CasoTeste(
            nome=entrada.stem,
            entrada=entrada.read_text(encoding="utf-8", errors="replace"),
            esperado=saida.read_text(encoding="utf-8", errors="replace") if saida.is_file() else "",
        ))
    return casos


def descobrir_casos(fonte):
    """Procura os testes de um .c nos locais convencionais."""
    fonte = Path(fonte)
    candidatos = [
        fonte.with_suffix(".testes"),
        fonte.with_suffix(".testes.txt"),
        fonte.parent / (fonte.stem + ".testes"),
    ]
    for c in candidatos:
        if c.is_file():
            return ler_arquivo_testes(c), c
    for pasta in (fonte.parent / "testes" / fonte.stem,
                  fonte.parent / (fonte.stem + ".testes.d")):
        if pasta.is_dir():
            return ler_pasta_testes(pasta), pasta
    return [], None


_NUMERO = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def _normalizar(texto, exato=False):
    """Quebra em linhas comparaveis, tolerando espacos extras e linhas vazias no fim."""
    linhas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not exato:
        linhas = [re.sub(r"[ \t]+", " ", l).strip() for l in linhas]
    while linhas and not linhas[-1].strip():
        linhas.pop()
    return linhas


def _linhas_iguais(a, b, tolerancia):
    if a == b:
        return True
    if tolerancia is None:
        return False
    ta, tb = a.split(), b.split()
    if len(ta) != len(tb):
        return False
    for x, y in zip(ta, tb):
        if x == y:
            continue
        # tolera virgula decimal, comum em saidas em portugues
        nx, ny = x.replace(",", "."), y.replace(",", ".")
        if _NUMERO.match(nx) and _NUMERO.match(ny):
            if abs(float(nx) - float(ny)) <= tolerancia:
                continue
        return False
    return True


def comparar(esperado, obtido, exato=False, tolerancia=None):
    """Devolve (igual, indice_da_primeira_linha_diferente)."""
    a = _normalizar(esperado, exato)
    b = _normalizar(obtido, exato)
    for i in range(max(len(a), len(b))):
        la = a[i] if i < len(a) else None
        lb = b[i] if i < len(b) else None
        if la is None or lb is None or not _linhas_iguais(la, lb, tolerancia):
            return False, i + 1
    return True, 0


def formatar_diferenca(esperado, obtido, linha_erro, exato=False):
    """Mostra esperado x obtido lado a lado, destacando a linha divergente."""
    a = _normalizar(esperado, exato)
    b = _normalizar(obtido, exato)
    largura = max([len(x) for x in a] + [len(x) for x in b] + [12])
    largura = min(largura, 44)

    out = []
    cab = "  %-4s %-*s   %s" % ("#", largura, "ESPERADO", "OBTIDO")
    out.append(cores.fraco(cab))
    total = max(len(a), len(b))
    inicio = max(0, linha_erro - 3) if linha_erro else 0
    fim = min(total, (linha_erro + 2) if linha_erro else total)
    if inicio > 0:
        out.append(cores.fraco("  ... %d linha(s) iguais omitidas" % inicio))

    for i in range(inicio, fim):
        la = a[i] if i < len(a) else cores.fraco("(nada)")
        lb = b[i] if i < len(b) else cores.fraco("(nada)")
        crua_a = a[i] if i < len(a) else "(nada)"
        crua_b = b[i] if i < len(b) else "(nada)"
        marca = " "
        if not _linhas_iguais(crua_a, crua_b, None):
            marca = cores.erro("!")
            la = cores.ok(crua_a[:largura])
            lb = cores.erro(crua_b[:largura])
        preenche = " " * max(0, largura - len(crua_a[:largura]))
        out.append("%s %-4d %s%s   %s" % (marca, i + 1, la, preenche, lb))
    if fim < total:
        out.append(cores.fraco("  ... mais %d linha(s)" % (total - fim)))
    return "\n".join("   " + l for l in out)


MODELO_ARQUIVO_TESTES = """\
# Casos de teste deste exercicio.
# Cada bloco tem a entrada que o programa recebe e a saida que ele deve imprimir.
# Linhas iniciadas por # sao ignoradas apenas fora dos blocos.

=== ENTRADA soma simples
2 3
=== SAIDA
5

=== ENTRADA numeros negativos
-4 10
=== SAIDA
6
"""
