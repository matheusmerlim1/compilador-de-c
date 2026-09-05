"""Interface de linha de comando do verificador de exercicios em C."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import compilar as mod_compilar
from . import cores, diagnosticos, executar, testes, toolchain

VERSAO = "1.0"
PASTA_BUILD = "build"


# ----------------------------------------------------------------------------
# utilidades de apresentacao
# ----------------------------------------------------------------------------

def cabecalho(texto):
    print()
    print(cores.titulo("== " + texto))


def _achar_compilador(args):
    comp = toolchain.detectar(getattr(args, "compilador", None))
    if comp is None:
        print(cores.erro("ERRO: nenhum compilador C encontrado."))
        print()
        print(toolchain.INSTRUCOES_INSTALACAO)
        sys.exit(3)
    return comp


def _pasta_build(fonte):
    return Path(fonte).parent / PASTA_BUILD


def _mostrar_saida_programa(res, prefixo="saida do programa"):
    if res.saida.strip():
        print("   " + cores.fraco(prefixo + ":"))
        for linha in res.saida.rstrip().splitlines()[:40]:
            print("     " + cores.c("|", "cinza") + " " + linha)
        extra = len(res.saida.rstrip().splitlines()) - 40
        if extra > 0:
            print("     " + cores.fraco("... mais %d linha(s)" % extra))
    if res.erros.strip():
        print("   " + cores.aviso("mensagens de erro do programa (stderr):"))
        for linha in res.erros.rstrip().splitlines()[:20]:
            print("     " + cores.c("|", "cinza") + " " + linha)


def _relatar_falha_execucao(res):
    if res.motivo:
        print("   " + cores.erro("FALHOU: " + res.motivo))
    if res.dica:
        print("   " + cores.c("provavel causa:", "ciano") + " " + res.dica)


# ----------------------------------------------------------------------------
# etapa de compilacao compartilhada pelos comandos
# ----------------------------------------------------------------------------

def _compilar_fonte(fonte, comp, args, silencioso=False):
    """Compila e imprime o relatorio. Devolve o ResultadoCompilacao."""
    fonte = Path(fonte).resolve()
    destino = mod_compilar.caminho_saida(fonte, _pasta_build(fonte))
    res = mod_compilar.compilar(
        comp, [fonte], destino,
        otimizar=getattr(args, "otimizar", False),
        sanitizar=getattr(args, "sanitizar", False),
    )
    erros, avisos = diagnosticos.contar(res.diags)

    if not silencioso:
        if res.sanitizador_indisponivel:
            print("   " + cores.aviso(
                "este compilador nao tem as bibliotecas do sanitizador; "
                "compilei sem elas"))
        if res.diags:
            texto = diagnosticos.formatar(res.diags, fonte.parent,
                                          mostrar_avisos=not getattr(args, "sem_avisos", False))
            if texto.strip():
                print()
                print(texto)

        if res.sucesso:
            resumo = cores.ok("compilou")
            if avisos:
                resumo += cores.aviso("  (%d aviso%s)" % (avisos, "s" if avisos > 1 else ""))
            print("   " + resumo)
        else:
            print("   " + cores.erro("nao compilou: %d erro(s)" % max(erros, 1)))
            if erros == 0 and res.saida_bruta.strip():
                # Falhou sem nenhum diagnostico de erro reconhecido: sem isto a
                # causa real ficaria invisivel atras dos avisos.
                print(cores.fraco(res.saida_bruta.strip()[:2000]))
    return res


# ----------------------------------------------------------------------------
# comandos
# ----------------------------------------------------------------------------

def cmd_verificar(args):
    comp = _achar_compilador(args)
    fontes = _coletar_fontes(args.alvo)
    if not fontes:
        return 2

    falhas = 0
    for fonte in fontes:
        cabecalho("Verificando " + fonte.name)
        res = _compilar_fonte(fonte, comp, args)
        if not res.sucesso:
            falhas += 1
    print()
    if falhas:
        print(cores.erro("%d de %d arquivo(s) com erro de compilacao." % (falhas, len(fontes))))
        return 1
    print(cores.ok("Todos os %d arquivo(s) compilaram." % len(fontes)))
    return 0


def cmd_rodar(args):
    comp = _achar_compilador(args)
    fonte = Path(args.alvo)
    if not fonte.is_file():
        print(cores.erro("Arquivo nao encontrado: " + str(fonte)))
        return 2

    cabecalho("Compilando " + fonte.name)
    res = _compilar_fonte(fonte, comp, args)
    if not res.sucesso:
        print()
        print(cores.erro("Corrija os erros acima antes de rodar."))
        return 1

    cabecalho("Executando " + fonte.stem)
    entrada = None
    if args.entrada:
        entrada = Path(args.entrada).read_text(encoding="utf-8", errors="replace")
    elif not sys.stdin.isatty():
        entrada = sys.stdin.read()

    if entrada is None:
        # terminal livre: o usuario digita as entradas normalmente
        print(cores.fraco("   (digite as entradas normalmente; Ctrl+C interrompe)"))
        print(cores.regua())
        exe = executar.executar_interativo(res.executavel, args.args, cwd=fonte.parent)
        print(cores.regua())
    else:
        exe = executar.executar(res.executavel, entrada=entrada, args=args.args,
                                timeout=args.tempo, cwd=fonte.parent)
        _mostrar_saida_programa(exe)

    print()
    if exe.sucesso:
        print("   " + cores.ok("terminou normalmente") +
              cores.fraco("  (%.3fs)" % exe.tempo))
        return 0
    _relatar_falha_execucao(exe)
    if (not getattr(args, "sanitizar", False) and not res.sanitizador_indisponivel
            and exe.codigo != 0 and not exe.expirou):
        print("   " + cores.fraco("dica: rode com --sanitizar para descobrir a linha exata."))
    return 1


def cmd_testar(args):
    comp = _achar_compilador(args)
    fontes = _coletar_fontes(args.alvo)
    if not fontes:
        return 2

    total_ok = total_casos = 0
    arquivos_com_problema = 0

    for fonte in fontes:
        cabecalho("Testando " + fonte.name)
        res = _compilar_fonte(fonte, comp, args)
        if not res.sucesso:
            arquivos_com_problema += 1
            continue

        casos, origem = testes.descobrir_casos(fonte)
        if not casos:
            print("   " + cores.aviso("sem casos de teste") + cores.fraco(
                "  (crie " + fonte.stem + ".testes -- veja: python cc.py novo --ajuda-testes)"))
            continue
        print("   " + cores.fraco("%d caso(s) em %s" % (len(casos), Path(origem).name)))
        print()

        passou_todos = True
        for caso in casos:
            total_casos += 1
            exe = executar.executar(res.executavel, entrada=caso.entrada + "\n",
                                    args=caso.args, timeout=args.tempo, cwd=fonte.parent)

            if exe.expirou or (exe.codigo != 0 and not caso.esperado):
                print("   " + cores.erro("X") + " " + caso.nome)
                _relatar_falha_execucao(exe)
                passou_todos = False
                continue
            if exe.codigo != 0:
                print("   " + cores.erro("X") + " " + caso.nome)
                _relatar_falha_execucao(exe)
                _mostrar_saida_programa(exe, "saida antes de quebrar")
                passou_todos = False
                continue

            igual, linha_erro = testes.comparar(
                caso.esperado, exe.saida,
                exato=args.exato, tolerancia=args.tolerancia)

            if igual:
                total_ok += 1
                print("   " + cores.ok("v") + " " + caso.nome +
                      cores.fraco("  (%.3fs)" % exe.tempo))
            else:
                passou_todos = False
                print("   " + cores.erro("X") + " " + caso.nome +
                      cores.fraco("  saida diferente na linha %d" % linha_erro))
                if caso.entrada.strip():
                    print("   " + cores.fraco("entrada: " +
                          caso.entrada.strip().replace("\n", " | ")[:70]))
                print(testes.formatar_diferenca(caso.esperado, exe.saida,
                                                linha_erro, args.exato))
                print()

        if not passou_todos:
            arquivos_com_problema += 1

    print()
    print(cores.regua())
    if total_casos:
        pinta = cores.ok if total_ok == total_casos else cores.erro
        print(pinta("%d de %d caso(s) passaram." % (total_ok, total_casos)))
    if arquivos_com_problema:
        print(cores.erro("%d arquivo(s) com problema." % arquivos_com_problema))
        return 1
    if not total_casos:
        print(cores.aviso("Nenhum caso de teste foi executado."))
        return 0
    return 0


def cmd_tudo(args):
    """Compila e testa tudo que houver na pasta, imprimindo um placar."""
    comp = _achar_compilador(args)
    pasta = Path(args.alvo or ".")
    fontes = _coletar_fontes(pasta)
    if not fontes:
        return 2

    print(cores.titulo("Verificando %d exercicio(s) com %s" % (len(fontes), comp.nome)))
    print(cores.regua(70))

    # Cada linha e (arquivo, rotulo_sem_cor, funcao_de_cor, detalhe) para que o
    # alinhamento use o tamanho do texto puro, e nao o do texto com codigos ANSI.
    linhas = []
    houve_falha = False
    for fonte in fontes:
        res = _compilar_fonte(fonte, comp, args, silencioso=True)
        erros, avisos = diagnosticos.contar(res.diags)

        if not res.sucesso:
            linhas.append((fonte, "NAO COMPILA", cores.erro, "%d erro(s)" % max(erros, 1)))
            houve_falha = True
            continue

        casos, _ = testes.descobrir_casos(fonte)
        if not casos:
            # Sem casos de teste nao da para conferir a saida, mas ainda vale
            # rodar uma vez: se quebrar sozinho, o exercicio tem problema.
            exe = executar.executar(res.executavel, entrada="",
                                    timeout=args.tempo, cwd=fonte.parent)
            if exe.codigo != 0 and not exe.expirou:
                linhas.append((fonte, "QUEBRA", cores.aviso,
                               "compila, mas falha ao executar"))
            else:
                detalhe = "%d aviso(s)" % avisos if avisos else "sem testes"
                linhas.append((fonte, "compila", cores.ok, detalhe))
            continue

        ok = 0
        for caso in casos:
            exe = executar.executar(res.executavel, entrada=caso.entrada + "\n",
                                    args=caso.args, timeout=args.tempo, cwd=fonte.parent)
            if exe.sucesso and testes.comparar(caso.esperado, exe.saida,
                                               args.exato, args.tolerancia)[0]:
                ok += 1
        if ok == len(casos):
            linhas.append((fonte, "OK", cores.ok, "%d/%d testes" % (ok, len(casos))))
        else:
            linhas.append((fonte, "FALHA", cores.erro, "%d/%d testes" % (ok, len(casos))))
            houve_falha = True

    largura_nome = max(len(f.name) for f, _, _, _ in linhas) + 2
    largura_estado = max(len(r) for _, r, _, _ in linhas) + 2
    for fonte, rotulo, pinta, detalhe in linhas:
        espaco = " " * (largura_estado - len(rotulo))
        print("  %-*s %s%s%s" % (largura_nome, fonte.name,
                                 pinta(rotulo), espaco, cores.fraco(detalhe)))

    print(cores.regua(70))
    if houve_falha:
        print(cores.erro("Ha exercicios com problema. Rode:") +
              cores.fraco("  python cc.py testar <arquivo.c>") +
              cores.erro(" para ver os detalhes."))
        return 1
    print(cores.ok("Tudo certo."))
    return 0


def cmd_novo(args):
    if args.ajuda_testes:
        print(cores.titulo("Formato do arquivo de testes"))
        print()
        print(testes.MODELO_ARQUIVO_TESTES)
        print(cores.fraco(
            "Salve como <nome_do_exercicio>.testes na mesma pasta do .c\n"
            "Alternativa: uma pasta testes/<nome_do_exercicio>/ com arquivos 01.in e 01.out"))
        return 0

    if not args.nome:
        print(cores.erro("Informe o nome: python cc.py novo exercicio1"))
        return 2

    nome = args.nome[:-2] if args.nome.endswith(".c") else args.nome
    destino = Path(nome + ".c")
    if destino.exists():
        print(cores.erro("Ja existe: " + str(destino)))
        return 2

    destino.write_text(MODELO_C, encoding="utf-8")
    arq_testes = Path(nome + ".testes")
    if not arq_testes.exists():
        arq_testes.write_text(testes.MODELO_ARQUIVO_TESTES, encoding="utf-8")

    print(cores.ok("criado: ") + str(destino))
    print(cores.ok("criado: ") + str(arq_testes))
    print()
    print(cores.fraco("Agora rode:  python cc.py rodar " + str(destino)))
    return 0


def cmd_doutor(args):
    print(cores.titulo("Diagnostico do ambiente"))
    print()
    print("  Python      " + sys.version.split()[0])
    print("  Sistema     " + sys.platform)
    print("  Pasta       " + str(Path.cwd()))
    print()

    comp = toolchain.detectar(getattr(args, "compilador", None))
    if comp:
        print("  " + cores.ok("compilador encontrado"))
        print("     nome     " + comp.nome)
        print("     caminho  " + comp.caminho)
        print("     versao   " + comp.versao)
        print()
        ok = _teste_de_fumaca(comp)
        return 0 if ok else 1

    print("  " + cores.erro("nenhum compilador C encontrado"))
    print()
    if args.instalar:
        return _instalar_gcc()
    print(toolchain.INSTRUCOES_INSTALACAO)
    return 3


def _teste_de_fumaca(comp):
    """Compila e roda um programa minimo para confirmar que a cadeia funciona."""
    import tempfile
    print("  Testando a cadeia de compilacao...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fonte = tmp / "teste.c"
        fonte.write_text(
            '#include <stdio.h>\n#include <math.h>\n'
            'int main(void){ printf("%d\\n", (int)sqrt(16.0)); return 0; }\n',
            encoding="utf-8")
        destino = mod_compilar.caminho_saida(fonte, tmp)
        res = mod_compilar.compilar(comp, [fonte], destino)
        if not res.sucesso:
            print("  " + cores.erro("o compilador falhou ao compilar um programa minimo:"))
            print(cores.fraco(res.saida_bruta[:1500]))
            return False
        exe = executar.executar(destino, entrada="", timeout=15, cwd=tmp)
        if exe.saida.strip() == "4":
            print("  " + cores.ok("tudo funcionando: compilou, ligou a math e executou."))
            return True
        print("  " + cores.aviso("compilou, mas a saida veio inesperada: " + repr(exe.saida)))
        return False


def _instalar_gcc():
    if os.name != "nt":
        print(cores.aviso("Instalacao automatica so esta disponivel no Windows."))
        print(toolchain.INSTRUCOES_INSTALACAO)
        return 3
    if not shutil.which("winget"):
        print(cores.erro("winget nao esta disponivel nesta maquina."))
        print(toolchain.INSTRUCOES_INSTALACAO)
        return 3

    pacote = "BrechtSanders.WinLibs.POSIX.UCRT"
    print(cores.aviso("Vou instalar o GCC via winget (pacote %s)." % pacote))
    print(cores.fraco("Isso baixa cerca de 100 MB e pode pedir confirmacao do Windows."))
    resposta = input("Continuar? [s/N] ").strip().lower()
    if resposta not in ("s", "sim", "y"):
        print("Cancelado.")
        return 1

    cmd = ["winget", "install", "-e", "--id", pacote,
           "--accept-package-agreements", "--accept-source-agreements"]
    print(cores.fraco("$ " + " ".join(cmd)))
    codigo = subprocess.run(cmd).returncode
    if codigo != 0:
        print(cores.erro("A instalacao falhou (codigo %d)." % codigo))
        print(toolchain.INSTRUCOES_INSTALACAO)
        return codigo
    print()
    print(cores.ok("Instalado."))
    print(cores.aviso("FECHE e reabra o terminal para o PATH atualizar, "
                      "depois rode: python cc.py doutor"))
    return 0


def cmd_editor(args):
    """Abre a janela onde se escreve o codigo."""
    try:
        from .editor import abrir_editor
    except ImportError as e:
        print(cores.erro("Nao foi possivel abrir a janela: " + str(e)))
        print(cores.fraco("O Python precisa ter o tkinter instalado."))
        return 3

    try:
        abrir_editor(args.alvo)
    except Exception:
        # Rodando com pythonw nao existe terminal para mostrar o erro: sem isto
        # a janela simplesmente nao apareceria e nada explicaria o porque.
        import traceback

        detalhe = traceback.format_exc()
        registro = Path(__file__).resolve().parent.parent / "erro.log"
        try:
            registro.write_text(detalhe, encoding="utf-8")
        except OSError:
            registro = None
        print(cores.erro(detalhe))
        try:
            import tkinter.messagebox as mb
            import tkinter as tk

            raiz = tk.Tk()
            raiz.withdraw()
            mb.showerror(
                "Falha ao abrir o compilador",
                "A janela nao pode ser aberta.\n\n" + detalhe.strip().splitlines()[-1] +
                (("\n\nDetalhes em:\n" + str(registro)) if registro else ""))
            raiz.destroy()
        except Exception:
            pass
        return 1
    return 0


def cmd_limpar(args):
    pasta = Path(args.alvo or ".")
    removidas = 0
    for build in pasta.rglob(PASTA_BUILD):
        if build.is_dir():
            shutil.rmtree(build, ignore_errors=True)
            removidas += 1
            print(cores.fraco("removido: " + str(build)))
    print(cores.ok("%d pasta(s) de build removida(s)." % removidas))
    return 0


# ----------------------------------------------------------------------------
# apoio
# ----------------------------------------------------------------------------

def _coletar_fontes(alvo):
    """Aceita um arquivo .c, uma pasta, ou nada (= pasta atual)."""
    caminho = Path(alvo or ".")
    if caminho.is_file():
        if caminho.suffix != ".c":
            print(cores.erro("Esperava um arquivo .c, recebi: " + str(caminho)))
            return []
        return [caminho.resolve()]
    if caminho.is_dir():
        fontes = sorted(f.resolve() for f in caminho.rglob("*.c")
                        if PASTA_BUILD not in f.parts)
        if not fontes:
            print(cores.aviso("Nenhum arquivo .c encontrado em " + str(caminho.resolve())))
        return fontes
    print(cores.erro("Caminho nao encontrado: " + str(caminho)))
    return []


MODELO_C = """\
#include <stdio.h>

int main(void) {
    int a, b;

    scanf("%d %d", &a, &b);
    printf("%d\\n", a + b);

    return 0;
}
"""


EPILOGO = """\
exemplos:
  python cc.py rodar exercicio1.c            compila e executa (voce digita as entradas)
  python cc.py rodar exercicio1.c -e dados.txt   executa lendo a entrada de um arquivo
  python cc.py verificar exercicio1.c        so compila e aponta os erros
  python cc.py testar exercicio1.c           roda os casos de teste do exercicio
  python cc.py testar exercicios/            testa todos os .c da pasta
  python cc.py tudo                          placar de todos os exercicios
  python cc.py novo exercicio2               cria o .c e o arquivo de testes
  python cc.py novo --ajuda-testes           mostra o formato dos casos de teste
  python cc.py doutor                        confere se o compilador esta instalado
"""


def construir_parser():
    p = argparse.ArgumentParser(
        prog="cc.py",
        description="Compila, executa e testa exercicios em C, explicando os erros em portugues.",
        epilog=EPILOGO,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--versao", action="version", version="verificador de C " + VERSAO)

    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--compilador", help="forca um compilador (gcc, clang, cl)")
    comum.add_argument("--sem-cor", action="store_true", dest="sem_cor",
                       help="desliga as cores")
    comum.add_argument("--sem-avisos", action="store_true", dest="sem_avisos",
                       help="mostra so os erros, escondendo os avisos")
    comum.add_argument("--sanitizar", action="store_true",
                       help="liga os detectores de erro de memoria em tempo de execucao")
    comum.add_argument("--otimizar", action="store_true", help="compila com -O2")
    comum.add_argument("-t", "--tempo", type=float, default=10,
                       help="limite de segundos por execucao (padrao: 10)")

    testes_comuns = argparse.ArgumentParser(add_help=False)
    testes_comuns.add_argument("--exato", action="store_true",
                               help="exige espacos em branco identicos na comparacao")
    testes_comuns.add_argument("--tolerancia", type=float, default=None,
                               help="margem de erro para comparar numeros (ex.: 0.001)")

    sub = p.add_subparsers(dest="comando")

    s = sub.add_parser("rodar", parents=[comum], help="compila e executa um arquivo")
    s.add_argument("alvo", help="arquivo .c")
    s.add_argument("-e", "--entrada", help="arquivo com a entrada padrao do programa")
    s.add_argument("args", nargs="*", help="argumentos passados ao programa")
    s.set_defaults(func=cmd_rodar)

    s = sub.add_parser("verificar", parents=[comum], help="so compila e aponta os erros")
    s.add_argument("alvo", nargs="?", default=".", help="arquivo .c ou pasta")
    s.set_defaults(func=cmd_verificar)

    s = sub.add_parser("testar", parents=[comum, testes_comuns],
                       help="roda os casos de teste")
    s.add_argument("alvo", nargs="?", default=".", help="arquivo .c ou pasta")
    s.set_defaults(func=cmd_testar)

    s = sub.add_parser("tudo", parents=[comum, testes_comuns],
                       help="placar resumido de todos os exercicios")
    s.add_argument("alvo", nargs="?", default=".", help="pasta")
    s.set_defaults(func=cmd_tudo)

    s = sub.add_parser("novo", help="cria um exercicio novo com arquivo de testes")
    s.add_argument("nome", nargs="?", help="nome do exercicio (sem .c)")
    s.add_argument("--ajuda-testes", action="store_true", dest="ajuda_testes",
                   help="mostra o formato do arquivo de testes")
    s.set_defaults(func=cmd_novo)

    s = sub.add_parser("doutor", parents=[comum], help="diagnostica o ambiente")
    s.add_argument("--instalar", action="store_true",
                   help="tenta instalar o GCC pelo winget")
    s.set_defaults(func=cmd_doutor)

    s = sub.add_parser("editor", help="abre a janela para escrever e rodar codigo")
    s.add_argument("alvo", nargs="?", help="arquivo .c para abrir junto")
    s.set_defaults(func=cmd_editor)

    s = sub.add_parser("limpar", help="apaga as pastas build/")
    s.add_argument("alvo", nargs="?", default=".", help="pasta")
    s.set_defaults(func=cmd_limpar)

    return p


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = construir_parser()
    args = parser.parse_args(argv)
    cores.configurar(getattr(args, "sem_cor", False))

    if not getattr(args, "comando", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        print(cores.aviso("interrompido"))
        return 130
