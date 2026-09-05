"""Descoberta do compilador C instalado na maquina."""
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Locais onde o GCC costuma aparecer no Windows mesmo fora do PATH.
# Aceita * no meio do caminho. Util logo depois de instalar, quando o terminal
# aberto ainda esta com o PATH antigo.
_PALPITES_WINDOWS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*\mingw64\bin"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*\*\bin"),
    r"C:\msys64\ucrt64\bin",
    r"C:\msys64\mingw64\bin",
    r"C:\MinGW\bin",
    r"C:\mingw64\bin",
    r"C:\TDM-GCC-64\bin",
    r"C:\Program Files\mingw-w64",
    r"C:\Program Files (x86)\mingw-w64",
    r"C:\Strawberry\c\bin",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\mingw64\bin"),
    os.path.expandvars(r"%USERPROFILE%\scoop\apps\gcc\current\bin"),
    r"C:\ProgramData\chocolatey\bin",
]


@dataclass
class Compilador:
    nome: str        # gcc | clang | cl
    caminho: str
    versao: str

    @property
    def familia(self) -> str:
        return "msvc" if self.nome == "cl" else "gcc"

    def __str__(self) -> str:
        return f"{self.nome} {self.versao} ({self.caminho})"


def _versao(caminho: str, nome: str) -> str:
    try:
        if nome == "cl":
            p = subprocess.run([caminho], capture_output=True, text=True, timeout=15)
            linha = (p.stderr or p.stdout).strip().splitlines()[0]
        else:
            p = subprocess.run([caminho, "--version"], capture_output=True, text=True, timeout=15)
            linha = p.stdout.strip().splitlines()[0]
        return linha.strip()
    except Exception:
        return "versao desconhecida"


def _expandir(base: str):
    """Resolve um palpite que pode conter * no meio do caminho."""
    if "*" not in base:
        return [Path(base)]
    partes = Path(base).parts
    raiz = Path(partes[0])
    resto = str(Path(*partes[1:]))
    try:
        return sorted(raiz.glob(resto))
    except (OSError, ValueError):
        return []


def _procurar_em_palpites(exe: str) -> str | None:
    if os.name != "nt":
        return None
    alvo = exe + ".exe"
    for base in _PALPITES_WINDOWS:
        for p in _expandir(base):
            if not p.is_dir():
                continue
            direto = p / alvo
            if direto.is_file():
                return str(direto)
            # mingw-w64 costuma esconder o bin alguns niveis abaixo
            for achado in p.glob(f"*/*/bin/{alvo}"):
                return str(achado)
    return None


def detectar(preferido: str | None = None) -> Compilador | None:
    """Devolve o primeiro compilador utilizavel, ou None se nao houver nenhum."""
    ordem = [preferido] if preferido else ["gcc", "clang", "cc", "cl"]
    for nome in ordem:
        if not nome:
            continue
        caminho = shutil.which(nome) or _procurar_em_palpites(nome)
        if caminho:
            return Compilador(nome=("gcc" if nome == "cc" else nome),
                              caminho=caminho,
                              versao=_versao(caminho, nome))
    return None


INSTRUCOES_INSTALACAO = """\
Nenhum compilador C foi encontrado nesta maquina.

Como instalar (escolha UMA opcao):

  1) winget (mais simples no Windows 11):
       winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT
     Depois FECHE e reabra o terminal.

  2) MSYS2 (recomendado se voce for usar C com frequencia):
       winget install -e --id MSYS2.MSYS2
     Depois abra o "MSYS2 UCRT64" e rode:
       pacman -S mingw-w64-ucrt-x86_64-gcc

  3) Chocolatey:
       choco install mingw

Para instalar automaticamente pela opcao 1, rode:
    python cc.py doutor --instalar
"""
