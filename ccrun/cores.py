"""Cores ANSI para o terminal, com desligamento automatico quando nao ha suporte."""
import os
import sys

_ATIVO = True


def _habilitar_ansi_windows() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        for handle in (-11, -12):  # stdout, stderr
            h = k32.GetStdHandle(handle)
            modo = ctypes.c_uint32()
            if k32.GetConsoleMode(h, ctypes.byref(modo)):
                k32.SetConsoleMode(h, modo.value | 0x0004)
        return True
    except Exception:
        return False


def configurar(sem_cor: bool = False) -> None:
    global _ATIVO
    if sem_cor or os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        _ATIVO = False
        return
    _ATIVO = _habilitar_ansi_windows()


_CODIGOS = {
    "reset": "\033[0m",
    "negrito": "\033[1m",
    "fraco": "\033[2m",
    "vermelho": "\033[31m",
    "verde": "\033[32m",
    "amarelo": "\033[33m",
    "azul": "\033[34m",
    "magenta": "\033[35m",
    "ciano": "\033[36m",
    "cinza": "\033[90m",
    "verm_forte": "\033[91m",
    "verde_forte": "\033[92m",
}


def c(texto: str, *estilos: str) -> str:
    if not _ATIVO or not estilos:
        return texto
    prefixo = "".join(_CODIGOS.get(e, "") for e in estilos)
    return f"{prefixo}{texto}{_CODIGOS['reset']}"


def titulo(texto: str) -> str:
    return c(texto, "negrito", "ciano")


def ok(texto: str) -> str:
    return c(texto, "verde_forte")


def erro(texto: str) -> str:
    return c(texto, "verm_forte")


def aviso(texto: str) -> str:
    return c(texto, "amarelo")


def fraco(texto: str) -> str:
    return c(texto, "cinza")


def regua(largura: int = 60, char: str = "-") -> str:
    return fraco(char * largura)
