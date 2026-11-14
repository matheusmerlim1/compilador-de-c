"""Testes da atualizacao automatica, sem rede (o GitHub e simulado).

Rodar:  python -m unittest discover -s tests
"""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccrun import atualizador, novidades  # noqa: E402


class Versoes(unittest.TestCase):
    def test_compara_numeros_e_nao_texto(self):
        self.assertTrue(atualizador.mais_nova("v1.10", "1.9"))
        self.assertTrue(atualizador.mais_nova("v2.0", "1.5"))
        self.assertFalse(atualizador.mais_nova("v1.5", "1.5"))
        self.assertFalse(atualizador.mais_nova("v1.4", "1.5"))
        self.assertFalse(atualizador.mais_nova("", "1.5"))


class Marcas(unittest.TestCase):
    def test_separa_marcas_internas(self):
        argv, sem, pid = atualizador.separar_marcas(
            ["app.exe", "soma.c", "--sem-atualizar", "--aguardar-pid", "42"])
        self.assertEqual(argv, ["app.exe", "soma.c"])
        self.assertTrue(sem)
        self.assertEqual(pid, 42)

    def test_reabrir_nao_acumula_marcas(self):
        with mock.patch.object(atualizador, "empacotado", return_value=True), \
                mock.patch.object(sys, "executable", "C:/x/Compilador-de-C.exe"):
            cmd = atualizador.comando_reabrir(
                ["C:/x/Compilador-de-C.exe", "a.c", "--sem-atualizar", "--aguardar-pid", "7"], 99)
        self.assertEqual(cmd, ["C:/x/Compilador-de-C.exe", "a.c",
                               "--sem-atualizar", "--aguardar-pid", "99"])


class TrocaDoExe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.exe = Path(self.tmp.name) / "Compilador-de-C.exe"
        self.exe.write_bytes(b"MZ antigo")

    def tearDown(self):
        self.tmp.cleanup()

    def test_troca_e_guarda_o_antigo(self):
        novo = b"MZ" + b"\0" * 1_200_000
        atualizador.trocar_exe(self.exe, novo)
        self.assertEqual(self.exe.read_bytes(), novo)
        antigo = self.exe.with_name(self.exe.name + ".antigo")
        self.assertEqual(antigo.read_bytes(), b"MZ antigo")
        atualizador.limpar_antigo(self.exe)
        self.assertFalse(antigo.exists())

    def test_recusa_download_que_nao_e_programa(self):
        with self.assertRaises(ValueError):
            atualizador.trocar_exe(self.exe, b"<html>erro 404</html>" * 100000)
        self.assertEqual(self.exe.read_bytes(), b"MZ antigo")

    def test_via_exe_baixa_troca_e_grava_novidades(self):
        dados = Path(self.tmp.name) / "dados"
        novo = b"MZ" + b"\0" * 1_200_000
        with mock.patch.object(atualizador, "empacotado", return_value=True), \
                mock.patch.object(sys, "executable", str(self.exe)), \
                mock.patch.object(atualizador, "VERSAO", "1.5"), \
                mock.patch.object(atualizador, "pasta_dados", return_value=dados), \
                mock.patch.object(atualizador, "ultimo_release",
                                  return_value=("v1.6", "https://exemplo/exe")), \
                mock.patch.object(atualizador, "_baixar", return_value=novo), \
                mock.patch.object(atualizador, "titulos_github",
                                  return_value=["feat: coisa nova", "chore: limpeza"]):
            avisos = []
            atualizou, msg = atualizador.procurar_e_aplicar(avisos.append)
        self.assertTrue(atualizou, msg)
        self.assertEqual(self.exe.read_bytes(), novo)
        self.assertTrue(avisos and "1.6" in avisos[0])
        card = json.loads((dados / "novidades.json").read_text(encoding="utf-8"))
        self.assertEqual((card["de"], card["para"]), ("1.5", "1.6"))

    def test_mesma_versao_nao_baixa(self):
        with mock.patch.object(atualizador, "empacotado", return_value=True), \
                mock.patch.object(atualizador, "VERSAO", "1.6"), \
                mock.patch.object(atualizador, "ultimo_release",
                                  return_value=("v1.6", "https://exemplo/exe")), \
                mock.patch.object(atualizador, "_baixar") as baixar:
            atualizou, _ = atualizador.procurar_e_aplicar()
        self.assertFalse(atualizou)
        baixar.assert_not_called()


class SemInternet(unittest.TestCase):
    def test_sem_rede_segue_sem_erro(self):
        def falha(*a, **k):
            raise OSError("sem rede")
        with mock.patch.object(atualizador, "empacotado", return_value=True), \
                mock.patch.object(atualizador, "_baixar", side_effect=falha):
            self.assertEqual(atualizador.procurar_e_aplicar(),
                             (False, "sem conexão com o GitHub"))


class Zip(unittest.TestCase):
    def test_copia_por_cima_sem_tocar_nos_exercicios(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "exercicios").mkdir()
            (raiz / "exercicios" / "01_soma.c").write_text("meu codigo")
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr("compilador-de-c-main/ccrun/novo.py", "x = 1\n")
                z.writestr("compilador-de-c-main/exercicios/01_soma.c", "do github")
            trocados = atualizador.aplicar_zip(buf.getvalue(), raiz)
            self.assertEqual(trocados, ["ccrun/novo.py"])
            self.assertEqual((raiz / "exercicios" / "01_soma.c").read_text(), "meu codigo")


class Card(unittest.TestCase):
    def test_classifica_pelo_prefixo(self):
        nov, cor = novidades.classificar([
            "feat: programas com OpenMP rodam sem configurar nada",
            "fix(a11y): anel de foco visível",
            "chore: limpeza", "docs: README"])
        self.assertEqual(nov, ["Programas com OpenMP rodam sem configurar nada"])
        self.assertEqual(cor, ["Anel de foco visível"])

    def test_card_aparece_uma_vez(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "novidades.json").write_text(
                json.dumps({"de": "1.4", "para": "1.5", "titulos": []}), encoding="utf-8")
            self.assertEqual(novidades.pendentes(Path(tmp))["para"], "1.5")
            self.assertIsNone(novidades.pendentes(Path(tmp)))

    def test_sem_progresso_nao_abre_janela(self):
        with mock.patch.object(novidades, "_janela_de_espera") as janela:
            r = novidades.com_aviso(lambda progresso: (False, "nada"))
        self.assertEqual(r, (False, "nada"))
        janela.assert_not_called()


class AoAbrir(unittest.TestCase):
    def test_desligado_pela_variavel_e_tira_marcas(self):
        with mock.patch.object(sys, "argv", ["app.py", "a.c", "--sem-atualizar"]), \
                mock.patch.dict(os.environ, {"CC_SEM_ATUALIZAR": "1"}), \
                mock.patch.object(atualizador, "procurar_e_aplicar") as procurar, \
                mock.patch.object(novidades, "pendentes", return_value=None):
            self.assertFalse(atualizador.ao_abrir())
            self.assertEqual(sys.argv, ["app.py", "a.c"])
        procurar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
