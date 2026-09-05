"""Gera o icone do programa (recursos/compilador.ico).

Rodar so quando quiser mudar o desenho. Precisa de: pip install pillow
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent

FUNDO = (30, 30, 30, 255)      # mesmo cinza do editor
BORDA = (14, 99, 156, 255)     # azul do botao Rodar
LETRA = (78, 201, 176, 255)    # verde-agua do console
CURSOR = (86, 156, 214, 255)   # azul das palavras-chave


def desenhar(tam):
    esc = tam / 256
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    raio = int(46 * esc)

    d.rounded_rectangle([0, 0, tam - 1, tam - 1], radius=raio, fill=FUNDO)
    d.rounded_rectangle([0, 0, tam - 1, tam - 1], radius=raio,
                        outline=BORDA, width=max(1, int(6 * esc)))

    fonte = None
    for nome in ("consolab.ttf", "arialbd.ttf"):
        try:
            fonte = ImageFont.truetype(nome, int(150 * esc))
            break
        except OSError:
            continue
    if fonte is None:
        fonte = ImageFont.load_default()

    d.text((tam / 2, tam / 2 - int(10 * esc)), "C",
           font=fonte, fill=LETRA, anchor="mm")

    # tracinho embaixo, lembrando o cursor de um terminal
    d.rectangle([int(tam * 0.30), int(tam * 0.80),
                 int(tam * 0.70), int(tam * 0.80) + max(2, int(10 * esc))],
                fill=CURSOR)
    return img


def main():
    tamanhos = [16, 24, 32, 48, 64, 128, 256]
    imagens = [desenhar(t) for t in tamanhos]
    imagens[-1].save(AQUI / "compilador.ico", format="ICO",
                     sizes=[(t, t) for t in tamanhos])
    imagens[-1].save(AQUI / "compilador.png")
    print("icone gerado em", AQUI / "compilador.ico")


if __name__ == "__main__":
    main()
