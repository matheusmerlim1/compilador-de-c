"""Execucao do programa compilado, com limite de tempo e leitura do motivo da falha."""
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

# Codigos de saida do Windows para falhas graves.
_FALHAS_WINDOWS = {
    0xC0000005: ("Violacao de acesso a memoria (segmentation fault)",
                 "Voce acessou memoria invalida. Causas mais comuns:\n"
                 "     - indice fora do vetor (ex.: v[10] em um vetor de 10 posicoes)\n"
                 "     - ponteiro nao inicializado ou depois de free()\n"
                 "     - scanf sem & na variavel\n"
                 "     - strcpy em string sem espaco suficiente"),
    0xC0000094: ("Divisao inteira por zero",
                 "Teste o divisor antes: if (b != 0) { r = a / b; }"),
    0xC0000095: ("Estouro em operacao inteira", "Valor maior do que o tipo suporta."),
    0xC00000FD: ("Estouro de pilha (stack overflow)",
                 "Quase sempre e recursao infinita: falta o caso base da funcao recursiva.\n"
                 "     Tambem pode ser um vetor local gigante (declare fora do main ou use malloc)."),
    0xC0000409: ("Corrupcao de pilha detectada",
                 "Voce escreveu alem do fim de um vetor local."),
    0xC0000374: ("Corrupcao da memoria dinamica (heap)",
                 "Escrita fora do bloco de malloc, ou free() chamado duas vezes."),
    0xC000013A: ("Programa interrompido pelo usuario (Ctrl+C)", ""),
}

# Sinais do Unix.
_FALHAS_POSIX = {
    signal.SIGSEGV: ("Violacao de acesso a memoria (segmentation fault)",
                     "Indice fora do vetor, ponteiro invalido ou scanf sem &."),
    signal.SIGFPE: ("Erro aritmetico (divisao por zero)",
                    "Teste o divisor antes de dividir."),
    signal.SIGABRT: ("Programa abortado",
                     "Geralmente vem de assert() que falhou ou corrupcao de heap detectada."),
    signal.SIGILL: ("Instrucao ilegal", "Ponteiro de funcao invalido ou memoria corrompida."),
}
if hasattr(signal, "SIGBUS"):
    _FALHAS_POSIX[signal.SIGBUS] = ("Erro de barramento", "Acesso a memoria desalinhado ou invalido.")


@dataclass
class ResultadoExecucao:
    codigo: int
    saida: str
    erros: str
    tempo: float
    expirou: bool = False
    motivo: str = ""
    dica: str = ""

    @property
    def sucesso(self):
        return self.codigo == 0 and not self.expirou


def explicar_codigo(codigo):
    """Traduz um codigo de saida anormal em causa provavel + o que investigar."""
    if codigo == 0:
        return "", ""

    if os.name == "nt":
        sem_sinal = codigo & 0xFFFFFFFF
        if sem_sinal in _FALHAS_WINDOWS:
            return _FALHAS_WINDOWS[sem_sinal]
    if codigo < 0:
        sinal = -codigo
        if sinal in _FALHAS_POSIX:
            return _FALHAS_POSIX[sinal]
    if 0 < codigo < 256:
        return ("O programa terminou com codigo %d" % codigo,
                "Isso veio de um return diferente de zero no main, ou de exit(%d). "
                "Em exercicios o esperado e terminar com return 0." % codigo)
    return ("O programa terminou de forma anormal (codigo %d / 0x%X)" % (codigo, codigo & 0xFFFFFFFF),
            "Provavel acesso invalido de memoria. Rode de novo com --sanitizar para localizar.")


# Um programa preso em laco infinito pode imprimir centenas de MB em poucos
# segundos. Guardamos so o comeco, mas continuamos drenando o cano para o
# processo nao travar esperando espaco.
LIMITE_SAIDA = 1_000_000  # bytes


def _drenar(fluxo, balde):
    try:
        while True:
            pedaco = fluxo.read(8192)
            if not pedaco:
                break
            if balde["tamanho"] < LIMITE_SAIDA:
                balde["partes"].append(pedaco)
                balde["tamanho"] += len(pedaco)
            else:
                balde["cortado"] = True
    except (ValueError, OSError):
        pass
    finally:
        try:
            fluxo.close()
        except OSError:
            pass


def executar(executavel, entrada=None, args=None, timeout=10, cwd=None):
    """Roda o programa capturando a saida, com limite de tempo e de volume."""
    import threading

    cmd = [str(executavel)] + list(args or [])
    inicio = time.perf_counter()
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd) if cwd else None,
        )
    except OSError as e:
        return ResultadoExecucao(codigo=-1, saida="", erros=str(e), tempo=0.0,
                                 motivo="nao foi possivel executar o programa",
                                 dica=str(e))

    baldes = [{"partes": [], "tamanho": 0, "cortado": False} for _ in range(2)]
    leitores = [
        threading.Thread(target=_drenar, args=(proc.stdout, baldes[0]), daemon=True),
        threading.Thread(target=_drenar, args=(proc.stderr, baldes[1]), daemon=True),
    ]
    for t in leitores:
        t.start()

    try:
        proc.stdin.write(entrada or "")
    except (OSError, ValueError):
        pass  # o programa pode ter terminado antes de ler a entrada
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass

    expirou = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        expirou = True
        proc.kill()
        proc.wait()

    for t in leitores:
        t.join(timeout=2)
    decorrido = time.perf_counter() - inicio

    saida = "".join(baldes[0]["partes"])
    erros = "".join(baldes[1]["partes"])
    if baldes[0]["cortado"]:
        saida += "\n[saida cortada: passou de %d caracteres]" % LIMITE_SAIDA

    if expirou:
        return ResultadoExecucao(
            codigo=-1, saida=saida, erros=erros, tempo=decorrido, expirou=True,
            motivo="O programa passou de %gs e foi interrompido" % timeout,
            dica=("Causas comuns:\n"
                  "     - laco infinito (a condicao do while/for nunca fica falsa)\n"
                  "     - scanf esperando um dado que nunca chega\n"
                  "     - falta de incremento dentro do while"),
        )

    motivo, dica = explicar_codigo(proc.returncode)
    return ResultadoExecucao(
        codigo=proc.returncode,
        saida=saida,
        erros=erros,
        tempo=decorrido,
        motivo=motivo,
        dica=dica,
    )


class _ConsoleUTF8:
    """No Windows o console costuma estar em CP850, o que embaralha os acentos
    que o programa em C imprime. Troca para UTF-8 enquanto o programa roda."""

    def __enter__(self):
        self.anterior = None
        if os.name != "nt":
            return self
        try:
            import ctypes

            k32 = ctypes.windll.kernel32
            self.anterior = k32.GetConsoleOutputCP()
            k32.SetConsoleOutputCP(65001)
        except Exception:
            self.anterior = None
        return self

    def __exit__(self, *exc):
        if self.anterior:
            try:
                import ctypes

                ctypes.windll.kernel32.SetConsoleOutputCP(self.anterior)
            except Exception:
                pass
        return False


def executar_interativo(executavel, args=None, cwd=None):
    """Roda herdando o terminal, para o usuario digitar as entradas na mao."""
    cmd = [str(executavel)] + list(args or [])
    inicio = time.perf_counter()
    with _ConsoleUTF8():
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    decorrido = time.perf_counter() - inicio
    motivo, dica = explicar_codigo(proc.returncode)
    return ResultadoExecucao(proc.returncode, "", "", decorrido, motivo=motivo, dica=dica)
