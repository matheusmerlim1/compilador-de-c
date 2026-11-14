"""Atualizacao automatica: ao abrir, procura versao nova no GitHub e atualiza ANTES de rodar.

Regra da secao 12 do githubGuia. Tres jeitos de o programa estar instalado:

- .exe (o normal: baixado do release ou copiado pelo instalador) -> compara a versao
  embutida (ccrun/versao.py) com o ultimo release; se houver mais nova, baixa o .exe,
  renomeia o que esta rodando para .antigo (o Windows deixa renomear um .exe aberto,
  so nao deixa apagar), poe o novo no lugar e reabre.
- codigo-fonte com git (pasta de desenvolvimento) -> git fetch + merge --ff-only, so se
  nao houver alteracao local no codigo.
- codigo-fonte pelo ZIP do GitHub -> compara ccrun/versao.txt (preenchido pelo
  git archive via export-subst) com o ultimo commit; se mudou, baixa o ZIP do ramo e
  copia por cima, sem tocar em exercicios/ (o que a pessoa escreveu) nem em build/.

Sem internet, segue normalmente. Nunca levanta excecao.
Depois de atualizar, grava o que mudou em novidades.json: a versao nova mostra o card
"O que mudou" uma vez (ccrun/novidades.py).
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from .versao import VERSAO

REPO = "matheusmerlim1/compilador-de-c"
RAMO = "main"
NOME_EXE = "Compilador-de-C.exe"
PROTEGIDOS = {".git", "build", "dist", "exercicios"}
SEM_JANELA = 0x08000000 if sys.platform == "win32" else 0     # CREATE_NO_WINDOW
AGENTE = {"User-Agent": "compilador-de-c-atualizador",
          "Accept": "application/vnd.github+json"}
API = "https://api.github.com/repos/" + REPO

# marcas que o programa passa para a instancia reaberta
SEM_ATUALIZAR = "--sem-atualizar"
AGUARDAR_PID = "--aguardar-pid"


# ----------------------------------------------------------------- onde esta

def empacotado() -> bool:
    return bool(getattr(sys, "frozen", False))


def raiz_codigo() -> Path:
    """Pasta do projeto (onde fica cc.py) quando roda pelo codigo-fonte."""
    return Path(__file__).resolve().parent.parent


def pasta_dados() -> Path:
    """Onde guardar novidades.json: fora da pasta do programa, que pode ser Downloads."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "CompiladorDeC"


def _baixar(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE),
                                timeout=timeout) as r:
        return r.read()


def _json(url: str, timeout: float = 6):
    return json.loads(_baixar(url, timeout).decode("utf-8"))


# ------------------------------------------------------------------ versoes

def numeros(versao: str) -> tuple:
    """'v1.10' -> (1, 10). Texto sem numero -> ()."""
    return tuple(int(n) for n in re.findall(r"\d+", versao or ""))


def mais_nova(remota: str, local: str) -> bool:
    return bool(numeros(remota)) and numeros(remota) > numeros(local)


def _git(raiz: Path, *args, timeout=20) -> subprocess.CompletedProcess:
    # git escreve em UTF-8; sem encoding explicito o Python le como cp1252 e os
    # acentos dos titulos dos commits viram lixo no card de novidades
    return subprocess.run(["git", "-c", "safe.directory=*", "-c", "i18n.logOutputEncoding=utf-8",
                           "-C", str(raiz), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=SEM_JANELA)


def commit_local(raiz: Path) -> str:
    """Commit desta instalacao pelo codigo: do git, ou o gravado no ZIP."""
    if (raiz / ".git").exists():
        try:
            r = _git(raiz, "rev-parse", "HEAD")
            if r.returncode == 0:
                return r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    arq = raiz / "ccrun" / "versao.txt"
    if arq.exists():
        v = arq.read_text(encoding="utf-8").strip()
        if v and "$Format" not in v:
            return v
    return ""


def descricao_versao() -> str:
    """O que mostrar na barra: '1.5' no .exe, '1.5 (abc1234)' pelo codigo."""
    if empacotado():
        return VERSAO
    c = commit_local(raiz_codigo())
    return VERSAO + (" (" + c[:7] + ")" if c else "")


# --------------------------------------------------------------- novidades

def guardar_novidades(de: str, para: str, titulos: list[str]) -> None:
    pasta = pasta_dados()
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "novidades.json").write_text(
        json.dumps({"de": de, "para": para, "titulos": titulos},
                   ensure_ascii=False, indent=2), encoding="utf-8")


def titulos_github(antes: str, depois: str) -> list[str]:
    """Titulos dos commits entre duas versoes (tags ou commits), mais novo primeiro."""
    if antes:
        dados = _json(API + "/compare/" + antes + "..." + depois, timeout=10)
        commits = dados["commits"][::-1]
    else:  # versao antiga desconhecida: mostra as mudancas mais recentes
        commits = _json(API + "/commits?sha=" + RAMO + "&per_page=8", timeout=10)
    return [c["commit"]["message"].splitlines()[0] for c in commits]


# ---------------------------------------------------------------- .exe

def ultimo_release(timeout: float = 6):
    """(tag, url do .exe) do ultimo release, ou None sem internet / sem .exe."""
    try:
        dados = _json(API + "/releases/latest", timeout)
    except Exception:
        return None
    for asset in dados.get("assets", []):
        if asset.get("name") == NOME_EXE:
            return dados.get("tag_name", ""), asset["browser_download_url"]
    return None


def limpar_antigo(exe: Path | None = None) -> None:
    """Apaga o .exe da versao anterior, deixado para tras na ultima atualizacao."""
    exe = exe or Path(sys.executable)
    antigo = exe.with_name(exe.name + ".antigo")
    try:
        if antigo.exists():
            antigo.unlink()
    except OSError:
        pass   # a versao antiga ainda saindo: fica para a proxima abertura


def trocar_exe(exe: Path, novo: bytes) -> None:
    """Poe o .exe novo no lugar do que esta rodando."""
    if len(novo) < 1_000_000 or not novo.startswith(b"MZ"):
        raise ValueError("o arquivo baixado nao parece um programa do Windows")
    temporario = exe.with_name(exe.name + ".novo")
    antigo = exe.with_name(exe.name + ".antigo")
    temporario.write_bytes(novo)
    try:
        if antigo.exists():
            antigo.unlink()
        os.replace(exe, antigo)          # renomear um .exe aberto o Windows permite
    except OSError:
        temporario.unlink(missing_ok=True)
        raise
    try:
        os.replace(temporario, exe)
    except OSError:
        os.replace(antigo, exe)          # desfaz: o programa antigo continua valendo
        raise


def _via_exe(progresso=None) -> tuple[bool, str]:
    rel = ultimo_release()
    if rel is None:
        return False, "sem conexão com o GitHub"
    tag, url = rel
    if not mais_nova(tag, VERSAO):
        return False, "já está na versão mais nova (" + VERSAO + ")"
    if progresso:
        progresso("Baixando o Compilador de C " + tag.lstrip("v") + "…")
    novo = _baixar(url, timeout=120)
    trocar_exe(Path(sys.executable), novo)
    try:
        titulos = titulos_github("v" + VERSAO, tag)
    except Exception:
        titulos = []
    guardar_novidades(VERSAO, tag.lstrip("v"), titulos)
    return True, "atualizado para a versão " + tag.lstrip("v")


# ------------------------------------------------------- codigo-fonte

def _igual(a: bytes, b: bytes) -> bool:
    """Mesmo conteudo, ignorando CRLF/LF."""
    return a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")


def aplicar_zip(dados: bytes, raiz: Path) -> list[str]:
    """Copia o ZIP do GitHub por cima da pasta, sem tocar nos protegidos."""
    trocados = []
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nomes = z.namelist()
        prefixo = nomes[0].split("/")[0] + "/"            # "compilador-de-c-main/"
        for nome in nomes:
            if nome.endswith("/") or not nome.startswith(prefixo):
                continue
            rel = nome[len(prefixo):]
            if any(rel == p or rel.startswith(p + "/") for p in PROTEGIDOS):
                continue
            destino = raiz / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            novo = z.read(nome)
            if destino.exists() and _igual(destino.read_bytes(), novo):
                continue
            tmp = destino.with_name(destino.name + ".novo")
            tmp.write_bytes(novo)
            os.replace(tmp, destino)
            trocados.append(rel)
    return trocados


def _via_git(raiz: Path) -> tuple[bool, str]:
    if _git(raiz, "remote", "get-url", "origin").returncode != 0:
        return False, "sem repositório remoto"
    if _git(raiz, "fetch", "--quiet", "origin", RAMO, timeout=15).returncode != 0:
        return False, "sem conexão com o GitHub"
    atras = _git(raiz, "rev-list", "--count", "HEAD..origin/" + RAMO).stdout.strip()
    if atras in ("", "0"):
        return False, "já está na versão mais nova"
    if _git(raiz, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        return False, "há versão nova, mas existem alterações locais no código: atualize à mão"
    antes = commit_local(raiz)
    if _git(raiz, "merge", "--ff-only", "origin/" + RAMO).returncode != 0:
        return False, "há versão nova, mas o histórico local divergiu: atualize à mão"
    depois = commit_local(raiz)
    r = _git(raiz, "log", "--format=%s", antes + ".." + depois)
    titulos = [t for t in r.stdout.splitlines() if t.strip()] if r.returncode == 0 else []
    guardar_novidades(antes[:7], depois[:7], titulos)
    return True, "atualizado pelo git (" + atras + " alteração(ões))"


def _via_zip(raiz: Path) -> tuple[bool, str]:
    try:
        remoto = _json(API + "/commits/" + RAMO)["sha"]
    except Exception:
        return False, "sem conexão com o GitHub"
    local = commit_local(raiz)
    if local == remoto:
        return False, "já está na versão mais nova"
    dados = _baixar("https://codeload.github.com/" + REPO + "/zip/refs/heads/" + RAMO, 60)
    trocados = aplicar_zip(dados, raiz)
    try:
        titulos = titulos_github(local, remoto)
    except Exception:
        titulos = []
    guardar_novidades(local[:7], remoto[:7], titulos)
    return True, "atualizado para " + remoto[:7] + " (" + str(len(trocados)) + " arquivo(s))"


# ------------------------------------------------------------- entrada

def procurar_e_aplicar(progresso=None) -> tuple[bool, str]:
    """Devolve (atualizou, mensagem). Nunca levanta excecao."""
    try:
        if empacotado():
            return _via_exe(progresso)
        raiz = raiz_codigo()
        if (raiz / ".git").exists():
            return _via_git(raiz)
        return _via_zip(raiz)
    except Exception as e:
        return False, "falha ao procurar atualização: " + repr(e)


def comando_reabrir(argv: list[str], pid: int) -> list[str]:
    """Linha de comando da instancia nova: mesmos argumentos, sem procurar de novo."""
    limpos, pular = [], False
    for a in argv[1:]:                 # tira marcas de reinicios anteriores
        if pular:
            pular = False
        elif a == AGUARDAR_PID:
            pular = True
        elif a != SEM_ATUALIZAR:
            limpos.append(a)
    if empacotado():
        inicio = [sys.executable]
    else:
        python = Path(sys.executable)
        janela = python.with_name("pythonw.exe")
        inicio = [str(janela if janela.exists() else python), str(Path(argv[0]).resolve())]
    return inicio + limpos + [SEM_ATUALIZAR, AGUARDAR_PID, str(pid)]


def reabrir(argv: list[str]) -> None:
    """Abre uma instancia nova (com o codigo novo) que espera esta terminar."""
    flags = 0x00000200 | 0x00000008 if sys.platform == "win32" else 0  # NEW_GROUP | DETACHED
    subprocess.Popen(comando_reabrir(argv, os.getpid()), creationflags=flags, close_fds=True)


def aguardar_processo(pid: int, segundos: float = 30) -> None:
    if sys.platform != "win32":
        return
    import ctypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x00100000, False, pid)     # SYNCHRONIZE
    if h:
        k.WaitForSingleObject(h, int(segundos * 1000))
        k.CloseHandle(h)


def separar_marcas(argv: list[str]) -> tuple[list[str], bool, int | None]:
    """Tira as marcas internas de argv. Devolve (argv limpo, sem_atualizar, pid)."""
    limpos, sem, pid, i = [], False, None, 0
    while i < len(argv):
        a = argv[i]
        if a == SEM_ATUALIZAR:
            sem = True
        elif a == AGUARDAR_PID and i + 1 < len(argv):
            try:
                pid = int(argv[i + 1])
            except ValueError:
                pass
            i += 1
        else:
            limpos.append(a)
        i += 1
    return limpos, sem, pid


def ao_abrir() -> bool:
    """Chamado antes de abrir a janela. True = reabriu com a versao nova; saia agora.

    Tambem tira de sys.argv as marcas internas e mostra o card de novidades pendente.
    """
    argv_original = list(sys.argv)
    sys.argv[:], sem_atualizar, pid = separar_marcas(sys.argv)
    if pid:
        aguardar_processo(pid)          # a versao antiga terminando de sair
    if empacotado():
        limpar_antigo()

    if not sem_atualizar and os.environ.get("CC_SEM_ATUALIZAR") != "1":
        from . import novidades
        atualizou, _msg = novidades.com_aviso(procurar_e_aplicar)
        if atualizou:
            try:
                reabrir(argv_original)
                return True
            except OSError:
                pass   # nao conseguiu reabrir: segue com esta, a nova vale na proxima

    try:
        from . import novidades
        pendente = novidades.pendentes(pasta_dados())
        if pendente:
            novidades.mostrar_card(pendente)
    except Exception:
        _registrar_falha("card de novidades")
    return False


def _registrar_falha(onde: str) -> None:
    """Sem console (pythonw, .exe): guarda o erro em vez de sumir com ele."""
    import traceback
    try:
        pasta = pasta_dados()
        pasta.mkdir(parents=True, exist_ok=True)
        with open(pasta / "atualizador.log", "a", encoding="utf-8") as f:
            f.write("--- " + onde + "\n" + traceback.format_exc() + "\n")
    except OSError:
        pass
