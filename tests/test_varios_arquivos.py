"""Varios arquivos compilados juntos.

Rodar:  python -m unittest discover -s tests
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccrun import compilar, diagnosticos, toolchain  # noqa: E402


def escrever(pasta, nome, texto):
    (pasta / nome).write_text(texto, encoding="utf-8")


class Relacionados(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name)
        escrever(self.p, "no.h", "int dobro(int x);\n")
        escrever(self.p, "no.c", '#include "no.h"\nint dobro(int x) { return 2 * x; }\n')
        escrever(self.p, "lista.h", "int soma_dobros(int n);\n")
        escrever(self.p, "lista.c",
                 '#include "lista.h"\n#include "no.h"\n'
                 "int soma_dobros(int n) { int s = 0;\n"
                 "  for (int i = 1; i <= n; i++) s += dobro(i);\n  return s; }\n")
        escrever(self.p, "main.c",
                 '#include <stdio.h>\n#include "lista.h"\n'
                 'int main(void) { printf("%d\\n", soma_dobros(4)); return 0; }\n')

    def tearDown(self):
        self.tmp.cleanup()

    def test_segue_os_includes_locais_em_cadeia(self):
        nomes = [p.name for p in compilar.arquivos_relacionados(self.p / "main.c")]
        self.assertEqual(nomes, ["lista.c", "no.c"])

    def test_cabecalho_sem_c_e_includes_do_sistema_nao_entram(self):
        escrever(self.p, "so.h", "#define N 3\n")
        escrever(self.p, "x.c", '#include <stdio.h>\n#include "so.h"\nint main(void){return N;}\n')
        self.assertEqual(compilar.arquivos_relacionados(self.p / "x.c"), [])

    def test_include_circular_nao_trava(self):
        escrever(self.p, "a.h", '#include "b.h"\n')
        escrever(self.p, "b.h", '#include "a.h"\n')
        escrever(self.p, "y.c", '#include "a.h"\nint main(void){return 0;}\n')
        self.assertEqual(compilar.arquivos_relacionados(self.p / "y.c"), [])

    @unittest.skipUnless(toolchain.detectar() and shutil.which("gcc"), "precisa do GCC")
    def test_compila_e_roda_junto(self):
        from ccrun import executar
        fonte = self.p / "main.c"
        destino = self.p / "build" / "main.exe"
        r = compilar.compilar(toolchain.detectar(),
                              [fonte] + compilar.arquivos_relacionados(fonte), destino)
        self.assertTrue(r.sucesso, r.saida_bruta)
        self.assertEqual(executar.executar(destino, entrada="", timeout=15).saida.strip(), "20")


class DoisMain(unittest.TestCase):
    def test_traduz_multiple_definition_de_main(self):
        saida = ("ld.exe: C:/t/cc1.o: in function `main':\n"
                 "C:/proj/outro.c:2: multiple definition of `main'; "
                 "C:/t/cc2.o:C:/proj/main.c:4: first defined here\n"
                 "collect2.exe: error: ld returned 1 exit status\n")
        diags = diagnosticos.analisar_saida(saida)
        self.assertEqual(len(diags), 1)
        self.assertIn("main", diags[0].traducao)
        self.assertIn("outro.c", diags[0].traducao)


if __name__ == "__main__":
    unittest.main()
