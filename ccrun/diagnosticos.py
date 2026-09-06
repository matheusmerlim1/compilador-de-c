"""Le a saida do compilador, traduz para portugues e explica o que fazer."""
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import cores

# arquivo.c:12:5: error: mensagem [-Wflag]
# O (?:[A-Za-z]:)? no inicio aceita a letra de unidade do Windows (C:\..., H:\...).
_LINHA_GCC = re.compile(
    r"^(?P<arquivo>(?:[A-Za-z]:)?[^:\n]+?):(?P<linha>\d+):(?:(?P<coluna>\d+):)?\s+"
    r"(?P<nivel>error|warning|note|fatal error):\s+(?P<msg>.*)$"
)
# arquivo.c(12): error C2065: mensagem   (MSVC)
_LINHA_MSVC = re.compile(
    r"^(?P<arquivo>[^(\n]+?)\((?P<linha>\d+)\)\s*:\s+"
    r"(?P<nivel>error|warning|fatal error)\s+\w+\d+:\s+(?P<msg>.*)$"
)
# undefined reference to `funcao'   (erro de ligacao, sem numero de linha)
_LINK = re.compile(r"undefined reference to [`'\"](?P<simbolo>[^`'\"]+)['\"]")

NIVEL_PT = {
    "error": "ERRO",
    "fatal error": "ERRO FATAL",
    "warning": "AVISO",
    "note": "nota",
}


@dataclass
class Diagnostico:
    nivel: str
    arquivo: str = ""
    linha: int = 0
    coluna: int = 0
    mensagem: str = ""
    traducao: str = ""
    dica: str = ""
    notas: list = field(default_factory=list)

    @property
    def e_erro(self) -> bool:
        return self.nivel.startswith(("error", "fatal"))


# (regex na mensagem original, traducao, dica pratica)
# Os campos {nome} vem dos grupos nomeados capturados pela regex.
_REGRAS = [
    # A regra do ) vem antes da do ; porque "expected ')' before ';' token"
    # cita os dois e o problema real e o parenteses.
    (r"expected ['\"]?\)['\"]?",
     "Faltou fechar um parenteses ).",
     "Confira se todo ( aberto tem um ) correspondente nesta linha."),

    # Cobre tanto "expected ';' before X" quanto a lista
    # "expected '=', ',', ';', 'asm' or '__attribute__' before X",
    # que o GCC emite quando falta o ; no fim da declaracao anterior.
    (r"expected .*?';'.*? before",
     "Faltou um ponto e virgula (;).",
     "O ; que falta esta quase sempre no FINAL DA LINHA ANTERIOR, "
     "e nao na linha que o compilador apontou."),

    (r"expected declaration or statement at end of input",
     "O arquivo acabou antes de fechar tudo.",
     "Faltou uma chave de fechamento }. Confira a indentacao para achar o bloco aberto."),

    (r"expected ['\"]?\}['\"]?",
     "Faltou uma chave de fechamento }.",
     "Cada { precisa de um } correspondente."),

    (r"['\"](?P<n>\w+)['\"] undeclared",
     "A variavel ou nome '{n}' nao foi declarado.",
     "Declare antes de usar (ex.: int {n};) ou confira se digitou o nome errado."),

    (r"implicit declaration of function ['\"](?P<f>\w+)['\"]",
     "A funcao '{f}' foi usada sem ser declarada.",
     "Provavelmente falta um #include no topo do arquivo, ou a funcao foi definida "
     "depois do main sem ter um prototipo antes."),

    (r"format ['\"]%(?P<esp>\w+)['\"] expects argument of type ['\"](?P<t>[^'\"]+)\*['\"], "
     r"but argument (?P<n>\d+) has type",
     "No scanf, o argumento {n} deveria ser um endereco ({t}*).",
     "Faltou o & antes da variavel. Escreva: scanf(\"%{esp}\", &variavel);"),

    (r"format ['\"]%(?P<esp>\w+)['\"] expects argument of type ['\"](?P<t>[^'\"]+)['\"], "
     r"but argument (?P<n>\d+) has type ['\"](?P<t2>[^'\"]+)['\"]",
     "O formato %{esp} espera {t}, mas recebeu {t2} no argumento {n}.",
     "Use o formato certo: %d para int, %f para float/double no printf, "
     "%lf para double no scanf, %c para char, %s para string."),

    (r"too few arguments to function ['\"](?P<f>\w+)['\"]",
     "Faltam argumentos na chamada de '{f}'.",
     "Compare a chamada com a assinatura declarada da funcao."),

    (r"too many arguments to function ['\"](?P<f>\w+)['\"]",
     "Argumentos demais na chamada de '{f}'.",
     "Compare a chamada com a assinatura declarada da funcao."),

    (r"control reaches end of non-void function",
     "A funcao promete devolver um valor mas pode terminar sem return.",
     "Garanta um return em TODOS os caminhos, inclusive dentro de if/else."),

    (r"['\"](?P<v>\w+)['\"] (?:is|may be) used uninitialized",
     "A variavel '{v}' pode ser usada sem ter valor definido.",
     "Inicialize na declaracao: int {v} = 0;  Ler lixo de memoria gera resultado aleatorio."),

    (r"unused variable ['\"](?P<v>\w+)['\"]",
     "A variavel '{v}' foi declarada mas nunca usada.",
     "Nao quebra o programa; remova a linha para deixar o codigo limpo."),

    (r"unused parameter ['\"](?P<v>\w+)['\"]",
     "O parametro '{v}' nunca e usado dentro da funcao.",
     "Nao quebra o programa. Remova o parametro se ele nao for necessario."),

    (r"comparison between pointer and integer",
     "Comparacao entre um ponteiro e um numero.",
     "Para comparar strings use strcmp(a, b) == 0 (com #include <string.h>). "
     "Para char use aspas simples: 'a', e nao \"a\"."),

    (r"(?:assignment to|initialization of) ['\"][^'\"]*['\"] from incompatible pointer type",
     "Atribuicao entre tipos de ponteiro incompativeis.",
     "Confira se o tipo do ponteiro bate com o tipo do dado apontado."),

    (r"passing argument (?P<n>\d+) of ['\"](?P<f>\w+)['\"] makes pointer from integer",
     "O argumento {n} de '{f}' deveria ser um ponteiro, mas recebeu um numero.",
     "Provavelmente falta o & (endereco), ou voce passou o valor em vez do vetor."),

    (r"array subscript .* is (?:above|below) array bounds|"
     r"array subscript \d+ is outside array bounds",
     "Acesso fora dos limites do vetor.",
     "Indices validos vao de 0 ate tamanho-1. Reveja a condicao do for."),

    (r"stray .* in program",
     "Ha um caractere invalido no codigo.",
     "Geralmente e acento ou cedilha fora de aspas, ou aspas curvas copiadas da web. "
     "Reescreva a linha digitando manualmente."),

    (r"conflicting types for ['\"](?P<f>\w+)['\"]",
     "A funcao '{f}' foi declarada de duas formas diferentes.",
     "O prototipo e a definicao precisam ter o mesmo tipo de retorno e os mesmos parametros."),

    (r"redefinition of ['\"](?P<v>\w+)['\"]",
     "'{v}' foi definido mais de uma vez.",
     "Remova a declaracao duplicada."),

    (r"(?P<h>[\w./]+\.h): No such file or directory",
     "O arquivo de cabecalho '{h}' nao existe.",
     "Confira a grafia do #include. Cabecalhos do sistema usam <>, os seus usam aspas."),

    (r"lvalue required as left operand of assignment",
     "O lado esquerdo do = nao pode receber um valor.",
     "Erro classico: usar = (atribuicao) onde deveria ser == (comparacao), ou o contrario."),

    (r"suggest parentheses around assignment used as truth value",
     "Voce usou = (atribuicao) dentro de um if ou while.",
     "Para comparar use ==. Note que if (x = 5) sempre da verdadeiro E ALTERA o valor de x."),

    (r"division by zero",
     "Divisao por zero detectada ja na compilacao.",
     "Verifique o divisor antes de dividir."),

    (r"missing terminating [\"'] character",
     "Faltou fechar as aspas.",
     "Toda string precisa abrir e fechar com aspas na MESMA linha."),

    (r"invalid operands to binary",
     "Os tipos usados nessa operacao nao combinam.",
     "Nao da para somar ou comparar diretamente tipos incompativeis."),

    (r"expected identifier or ['\"]?\(['\"]? before",
     "O compilador encontrou algo inesperado nesse ponto.",
     "Confira a linha anterior: chave, parenteses ou ; fora do lugar."),

    (r"statement with no effect",
     "Esta instrucao nao faz nada.",
     "Classico no for: escrever  for(i; i<n; i++)  em vez de  for(i = 0; i<n; i++). "
     "O 'i' sozinho e lido e jogado fora. Se a variavel ja foi inicializada antes, "
     "deixe o campo vazio:  for(; i<n; i++)."),

    (r"value computed is not used",
     "O valor calculado nesta linha nao e guardado em lugar nenhum.",
     "Faltou atribuir o resultado a alguma variavel."),

    (r"multi-character character constant",
     "Aspas simples com mais de um caractere.",
     "Use aspas duplas para texto com mais de uma letra."),
]

_REGRAS_COMPILADAS = [(re.compile(p, re.IGNORECASE), t, d) for p, t, d in _REGRAS]

# Funcao usada -> cabecalho que precisa ser incluido.
_INCLUDES = {
    "printf": "stdio.h", "scanf": "stdio.h", "puts": "stdio.h", "gets": "stdio.h",
    "fgets": "stdio.h", "getchar": "stdio.h", "putchar": "stdio.h", "fopen": "stdio.h",
    "sprintf": "stdio.h", "fprintf": "stdio.h", "perror": "stdio.h", "fclose": "stdio.h",
    "malloc": "stdlib.h", "calloc": "stdlib.h", "realloc": "stdlib.h", "free": "stdlib.h",
    "exit": "stdlib.h", "atoi": "stdlib.h", "atof": "stdlib.h", "rand": "stdlib.h",
    "srand": "stdlib.h", "qsort": "stdlib.h", "abs": "stdlib.h", "system": "stdlib.h",
    "strlen": "string.h", "strcpy": "string.h", "strncpy": "string.h", "strcat": "string.h",
    "strcmp": "string.h", "strncmp": "string.h", "strchr": "string.h", "strstr": "string.h",
    "memset": "string.h", "memcpy": "string.h", "strtok": "string.h",
    "sqrt": "math.h", "pow": "math.h", "fabs": "math.h", "floor": "math.h", "ceil": "math.h",
    "sin": "math.h", "cos": "math.h", "tan": "math.h", "log": "math.h", "log10": "math.h",
    "round": "math.h", "exp": "math.h",
    "toupper": "ctype.h", "tolower": "ctype.h", "isdigit": "ctype.h", "isalpha": "ctype.h",
    "isspace": "ctype.h", "isupper": "ctype.h", "islower": "ctype.h", "isalnum": "ctype.h",
    "time": "time.h", "clock": "time.h", "difftime": "time.h",
    "bool": "stdbool.h", "true": "stdbool.h", "false": "stdbool.h",
    "INT_MAX": "limits.h", "INT_MIN": "limits.h",
}


def _preencher(texto, campos):
    """Troca {nome} pelo valor capturado.

    Nao usa str.format porque varias traducoes falam de chaves de bloco e
    trazem { e } literais no texto ("Faltou uma chave de fechamento }.").
    """
    for chave, valor in campos.items():
        texto = texto.replace("{" + chave + "}", valor)
    return texto


def _aplicar_regras(msg):
    for regex, traducao, dica in _REGRAS_COMPILADAS:
        m = regex.search(msg)
        if not m:
            continue
        campos = {k: v for k, v in (m.groupdict() or {}).items() if v is not None}
        return _preencher(traducao, campos), _preencher(dica, campos)
    return "", ""


# Cabecalhos do mundo Unix/Linux que simplesmente nao existem no Windows.
# O valor explica para que serve e o que usar no lugar.
_SO_NO_LINUX = {
    "sys/mman.h": ("mapeamento de memoria (mmap)",
                   "No Windows o equivalente e CreateFileMapping/MapViewOfFile, "
                   "de <windows.h>. Para exercicios de faculdade normalmente da "
                   "para usar malloc() de <stdlib.h>."),
    "sys/socket.h": ("rede (sockets)", "No Windows use <winsock2.h> e ligue a ws2_32."),
    "netinet/in.h": ("rede (enderecos IP)", "No Windows use <winsock2.h>."),
    "arpa/inet.h": ("rede (conversao de enderecos)", "No Windows use <winsock2.h>."),
    "netdb.h": ("rede (consulta de nomes)", "No Windows use <winsock2.h>."),
    "sys/wait.h": ("espera por processos filhos",
                   "E do modelo fork/wait do Unix, que o Windows nao tem."),
    "sys/ipc.h": ("comunicacao entre processos", "Nao existe no Windows."),
    "sys/shm.h": ("memoria compartilhada", "No Windows use CreateFileMapping."),
    "sys/sem.h": ("semaforos do Unix", "No Windows use <windows.h> ou <semaphore.h>."),
    "sys/select.h": ("espera por varios descritores", "No Windows use <winsock2.h>."),
    "termios.h": ("controle do terminal",
                  "No Windows use <conio.h> (getch, kbhit) ou <windows.h>."),
    "dlfcn.h": ("carregar bibliotecas em tempo de execucao",
                "No Windows use LoadLibrary, de <windows.h>."),
    "poll.h": ("espera por eventos", "No Windows use <winsock2.h>."),
    "pwd.h": ("dados de usuarios do sistema", "Nao existe no Windows."),
    "grp.h": ("dados de grupos do sistema", "Nao existe no Windows."),
    "sys/resource.h": ("limites de recursos", "Nao existe no Windows."),
    "syslog.h": ("registro do sistema", "Nao existe no Windows."),
}

# Cabecalhos validos, usados para adivinhar o que a pessoa quis digitar.
_CABECALHOS_CONHECIDOS = [
    "stdio.h", "stdlib.h", "string.h", "math.h", "ctype.h", "time.h",
    "limits.h", "float.h", "stdbool.h", "stddef.h", "stdint.h", "assert.h",
    "errno.h", "locale.h", "setjmp.h", "signal.h", "stdarg.h", "wchar.h",
    "wctype.h", "complex.h", "inttypes.h", "conio.h", "windows.h",
    "sys/types.h", "sys/stat.h", "sys/time.h", "unistd.h", "dirent.h",
    "fcntl.h", "pthread.h", "semaphore.h",
] + list(_SO_NO_LINUX)


def _dica_cabecalho(diag):
    """Explica um #include que nao existe: se e coisa de Linux, ou erro de digitacao."""
    m = re.search(r"([\w./+-]+\.h): No such file or directory", diag.mensagem)
    if not m:
        return
    pedido = m.group(1).replace("\\", "/")

    info = _SO_NO_LINUX.get(pedido)
    if info:
        para_que, alternativa = info
        diag.traducao = ("O cabecalho '" + pedido + "' e do Linux/Unix e nao existe "
                         "no Windows. Ele serve para " + para_que + ".")
        diag.dica = alternativa
        return

    import difflib

    parecidos = difflib.get_close_matches(pedido, _CABECALHOS_CONHECIDOS, n=1, cutoff=0.7)
    if parecidos:
        sugerido = parecidos[0]
        extra = ""
        if sugerido in _SO_NO_LINUX:
            extra = ("  Atencao: mesmo escrito certo, '" + sugerido +
                     "' e do Linux e nao existe no Windows.")
        diag.dica = ("Voce quis dizer  #include <" + sugerido + "> ?" + extra)


def _dica_include(diag):
    """Se a funcao desconhecida for conhecida nossa, diz exatamente qual #include falta."""
    m = (re.search(r"implicit declaration of function ['\"](\w+)['\"]", diag.mensagem)
         or re.search(r"['\"](\w+)['\"] undeclared", diag.mensagem))
    if not m:
        return
    header = _INCLUDES.get(m.group(1))
    if header:
        diag.dica = "Adicione no topo do arquivo:  #include <" + header + ">"


def analisar_saida(saida, familia="gcc"):
    """Converte o texto bruto do compilador em uma lista de diagnosticos."""
    diags = []
    padrao = _LINHA_MSVC if familia == "msvc" else _LINHA_GCC

    for bruta in saida.splitlines():
        linha = bruta.strip()
        m = padrao.match(linha)
        if m:
            g = m.groupdict()
            nivel = g["nivel"]
            msg = g["msg"].strip()
            if nivel == "note" and diags:
                if msg not in diags[-1].notas:
                    diags[-1].notas.append(msg)
                continue
            d = Diagnostico(
                nivel=nivel,
                arquivo=g["arquivo"],
                linha=int(g["linha"]),
                coluna=int(g.get("coluna") or 0),
                mensagem=msg,
            )
            # O GCC repete a mesma queixa como "incompatible implicit declaration
            # of built-in function" logo depois do erro principal. Nao adianta
            # mostrar duas vezes a mesma linha para quem esta aprendendo.
            if "incompatible implicit declaration" in msg and any(
                    x.linha == d.linha and x.arquivo == d.arquivo and
                    "implicit declaration of function" in x.mensagem
                    for x in diags[-3:]):
                continue

            d.traducao, d.dica = _aplicar_regras(msg)
            _dica_include(d)
            _dica_cabecalho(d)
            diags.append(d)
            continue

        ml = _LINK.search(linha)
        if ml:
            simbolo = ml.group("simbolo").lstrip("_")
            simbolo = simbolo.split("@")[0]  # WinMain@16 -> WinMain
            # A linha do ld traz caminhos enormes; guarda so a parte que interessa.
            d = Diagnostico(nivel="error",
                            mensagem="undefined reference to '" + simbolo + "'")
            # No MinGW a falta do main aparece como referencia perdida a WinMain.
            if simbolo in ("main", "WinMain"):
                d.traducao = "O programa nao tem a funcao main."
                d.dica = "Todo programa em C precisa de:  int main(void) { ... return 0; }"
            elif _INCLUDES.get(simbolo) == "math.h":
                d.traducao = ("A funcao matematica '" + simbolo +
                              "' nao foi encontrada na hora de ligar o programa.")
                d.dica = ("Falta ligar a biblioteca matematica (-lm). Esta ferramenta ja faz isso "
                          "automaticamente; confira se o #include <math.h> esta presente.")
            else:
                d.traducao = "A funcao '" + simbolo + "' foi usada mas nunca foi definida."
                d.dica = ("Voce declarou o prototipo mas esqueceu de escrever o corpo da funcao, "
                          "ou digitou o nome diferente na definicao.")
            diags.append(d)

    return diags


def _trecho_codigo(diag, raiz):
    """Mostra a linha do erro com a coluna marcada, e a anterior como contexto."""
    if not diag.arquivo or not diag.linha:
        return []
    caminho = Path(diag.arquivo)
    if not caminho.is_absolute():
        caminho = raiz / caminho
    if not caminho.is_file():
        return []
    try:
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    saida = []
    inicio = max(1, diag.linha - 1)
    for n in range(inicio, min(len(linhas), diag.linha) + 1):
        texto = linhas[n - 1]
        marcador = ">" if n == diag.linha else " "
        estilo = "negrito" if n == diag.linha else "cinza"
        numero = cores.fraco("%4d |" % n)
        saida.append("   " + marcador + " " + numero + " " + cores.c(texto, estilo))
    if diag.coluna:
        espacos = " " * (diag.coluna - 1)
        saida.append("     " + cores.fraco("     |") + " " + espacos + cores.erro("^"))
    return saida


def formatar(diags, raiz, mostrar_avisos=True):
    """Monta o relatorio legivel dos diagnosticos."""
    linhas = []
    for d in diags:
        if d.nivel == "warning" and not mostrar_avisos:
            continue
        rotulo = NIVEL_PT.get(d.nivel, d.nivel.upper())
        pinta = cores.erro if d.e_erro else cores.aviso
        local = (Path(d.arquivo).name + ":" + str(d.linha)) if d.arquivo else "ligacao (link)"
        if d.coluna:
            local += ":" + str(d.coluna)

        linhas.append(pinta(rotulo) + " " + cores.c(local, "negrito"))
        if d.traducao:
            linhas.append("   " + d.traducao)
            linhas.append("   " + cores.fraco("original: " + d.mensagem))
        else:
            linhas.append("   " + d.mensagem)
        linhas.extend(_trecho_codigo(d, raiz))
        if d.dica:
            linhas.append("   " + cores.c("como corrigir:", "ciano") + " " + d.dica)
        for nota in d.notas[:2]:
            linhas.append("   " + cores.fraco("nota: " + nota))
        linhas.append("")
    return "\n".join(linhas)


def contar(diags):
    erros = sum(1 for d in diags if d.e_erro)
    avisos = sum(1 for d in diags if d.nivel == "warning")
    return erros, avisos


# ---------------------------------------------------------------------------
# Revisao propria do codigo-fonte.
# Pega armadilhas classicas de iniciante que o compilador aceita calado.
# ---------------------------------------------------------------------------

# char letra;  (uma so letra, sem colchetes)
_DECL_CHAR = re.compile(r"\bchar\s+([A-Za-z_]\w*)\s*(?:=[^;,]*)?\s*[;,]")
# char nome[20];
_DECL_VETOR = re.compile(r"\bchar\s+([A-Za-z_]\w*)\s*\[")
_SCANF = re.compile(r"\bscanf\s*\(\s*\"([^\"]*)\"\s*,\s*([^)]*)\)")

# Uma linha que é só a chamada do scanf, sem ninguém guardar ou testar o
# retorno. "if (scanf(...))" e "r = scanf(...)" não casam aqui, de propósito.
_SCANF_SOLTO = re.compile(r"^scanf\s*\(.*\)\s*;\s*$")

_ABRE_LACO = re.compile(r"^\s*(while|for)\s*\(|^\s*do\b")


def _linhas_em_laco(linhas):
    """Numeros de linha que estao dentro de algum while/for/do.

    Conta chaves para saber onde o laço termina. Não entende todos os casos
    do C (um laço de uma linha só, sem chaves, não entra), mas cobre bem a
    forma como os exercícios são escritos.
    """
    dentro = set()
    pilha = []          # profundidade de chave onde cada laço começou
    profundidade = 0

    for n, bruta in enumerate(linhas, 1):
        linha = bruta.split("//")[0]

        comeca_laco = bool(_ABRE_LACO.match(linha))
        if pilha:
            dentro.add(n)

        for ch in linha:
            if ch == "{":
                profundidade += 1
                if comeca_laco and (not pilha or pilha[-1] != profundidade):
                    pilha.append(profundidade)
                    comeca_laco = False
            elif ch == "}":
                if pilha and pilha[-1] == profundidade:
                    pilha.pop()
                profundidade = max(0, profundidade - 1)

    return dentro


def revisar_fonte(caminho):
    """Le o .c e devolve avisos que o compilador nao emite."""
    caminho = Path(caminho)
    try:
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    texto = "\n".join(linhas)
    vetores = set(_DECL_VETOR.findall(texto))
    chars_simples = {n for n in _DECL_CHAR.findall(texto) if n not in vetores}

    dentro_de_laco = _linhas_em_laco(linhas)

    achados = []
    for n, linha in enumerate(linhas, 1):
        sem_comentario = linha.split("//")[0]

        # scanf cujo resultado ninguem confere. Se estiver dentro de um laço,
        # é a receita exata da repetição infinita: digitando algo que não
        # encaixa no formato, o scanf falha, não consome o que foi digitado,
        # e a volta seguinte tenta ler o mesmo texto de novo.
        if _SCANF_SOLTO.match(sem_comentario.strip()):
            if n in dentro_de_laco:
                achados.append(Diagnostico(
                    nivel="warning", arquivo=str(caminho), linha=n,
                    mensagem="scanf dentro de um laco sem conferir o retorno",
                    traducao="Este scanf esta dentro de um laco e ninguem "
                             "confere se a leitura deu certo.",
                    dica="Se for digitado algo fora do formato (uma letra onde "
                         "se espera numero), o scanf falha, o texto continua na "
                         "entrada e o laco repete para sempre. Confira o "
                         "retorno:\n"
                         "     if (scanf(\"%d\", &n) != 1) {\n"
                         "         while (getchar() != '\\n');   /* limpa a entrada */\n"
                         "         continue;\n"
                         "     }",
                ))
            else:
                achados.append(Diagnostico(
                    nivel="warning", arquivo=str(caminho), linha=n,
                    mensagem="scanf sem conferir o retorno",
                    traducao="Ninguem confere se este scanf conseguiu ler o "
                             "que pediu.",
                    dica="Digitar algo fora do formato nao da erro em C: a "
                         "variavel fica com o valor antigo e o programa segue "
                         "com um dado errado. O scanf devolve quantos valores "
                         "leu — compare com o esperado.",
                ))

        for formato, args in _SCANF.findall(sem_comentario):
            nomes = [a.strip().lstrip("&").strip() for a in args.split(",")]

            # %s lendo para dentro de um char solto: escreve a letra E o \0,
            # ou seja, no minimo 2 bytes num espaco de 1.
            if "%s" in formato:
                for nome in nomes:
                    if nome in chars_simples:
                        achados.append(Diagnostico(
                            nivel="warning", arquivo=str(caminho), linha=n,
                            mensagem="scanf(\"%s\") lendo para a variavel char '"
                                     + nome + "'",
                            traducao="'" + nome + "' guarda UMA letra, mas %s le uma "
                                     "palavra inteira e ainda grava um caractere "
                                     "invisivel de fim de texto.",
                            dica="Para ler uma unica letra troque por:  "
                                 "scanf(\" %c\", &" + nome + ");   "
                                 "(repare no espaco antes do %c). "
                                 "Se voce quer mesmo ler uma palavra, declare "
                                 "char " + nome + "[20];",
                        ))

            # %c colado no comeco pega o Enter que sobrou do scanf anterior
            if formato.startswith("%c"):
                achados.append(Diagnostico(
                    nivel="warning", arquivo=str(caminho), linha=n,
                    mensagem="scanf(\"%c\") sem espaco antes do %c",
                    traducao="Este %c vai capturar a tecla Enter que sobrou da "
                             "leitura anterior, em vez de esperar voce digitar.",
                    dica="Escreva um espaco antes:  scanf(\" %c\", ...)",
                ))

    return achados
