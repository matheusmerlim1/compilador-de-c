# Compilador de C

**Escreva, compile e teste exercícios em C numa janela só — com os erros do
compilador traduzidos para português e uma dica de como corrigir cada um.**

[**⬇ Baixar para Windows**](https://github.com/matheusmerlim1/compilador-de-c/releases/latest/download/Compilador-de-C.exe)
 · [Página do projeto](https://matheusmerlim1.github.io/compilador-de-c/)

<img src="recursos/compilador.png" width="96" alt="Ícone do Compilador de C">

Não substitui o compilador: usa o **GCC** por baixo e trabalha em cima do que
ele responde.

---

## O problema que ele resolve

Quem está aprendendo C trava na mensagem do compilador, não no algoritmo.
O GCC diz:

```
media.c:7:5: error: expected '=', ',', ';', 'asm' or '__attribute__' before 'float'
```

Este programa diz:

```
ERRO  linha 7
   Faltou um ponto e vírgula (;).
   original: expected '=', ',', ';', 'asm' or '__attribute__' before 'float'
     6 |     float n1, n2, n3
   > 7 |     float media;
   como corrigir: O ; que falta está quase sempre no FINAL DA LINHA ANTERIOR,
                  e não na linha que o compilador apontou.
```

---

## Instalação

1. Baixe o **`Compilador-de-C.exe`** pelo link acima e dê dois cliques — já abre,
   sem precisar de Python.
2. Para instalar de vez (atalhos + *Abrir com*), baixe o repositório e rode
   `instalador\INSTALAR.bat`.

O instalador não pede administrador: copia para a sua pasta de usuário, cria os
atalhos, registra o programa no **Abrir com** dos arquivos `.c` e adiciona uma
entrada em *Aplicativos e Recursos*. Para remover, use o
`instalador\DESINSTALAR.bat` ou o atalho *Desinstalar* no Menu Iniciar.

### É preciso ter um compilador C

O programa é uma interface para o GCC. Se não houver um na máquina, o instalador
se oferece para baixá-lo, e o próprio programa mostra o passo a passo. Manual:

```
winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT
```

Depois de instalar, feche e reabra as janelas para o PATH atualizar. A ferramenta
também procura o GCC nos lugares comuns, mesmo que ele não esteja no PATH.

### Rodando pelo código-fonte

Precisa de **Python 3.10+** (o Tkinter já vem junto):

```
python cc.py editor
```

Ou dê duplo clique em `Abrir Compilador.pyw`.

---

## Como usar

Escreva o código em cima, aperte **F5**, e o resultado aparece embaixo.

| Tecla | Botão | O que faz |
|---|---|---|
| <kbd>F5</kbd> | ▶ Rodar | compila e executa no console da janela |
| <kbd>Esc</kbd> | ■ Parar | mata o programa que está rodando |
| <kbd>Shift</kbd>+<kbd>F5</kbd> | Terminal | roda numa janela preta separada |
| <kbd>F7</kbd> | Verificar | só compila e lista os erros |
| <kbd>F6</kbd> | Testar | confere a saída contra os casos de teste |
| <kbd>Ctrl</kbd>+<kbd>S</kbd> | Salvar | grava o arquivo `.c` |

Quando há erro, a linha fica **marcada em vermelho no editor** e a aba *Erros*
explica o problema em português.

Não precisa salvar antes de rodar: um arquivo sem nome é compilado a partir de
uma cópia temporária.

### O console

Depois do F5, a aba *Saída* vira um console de verdade: as perguntas do programa
aparecem **na hora** e você digita a resposta ali mesmo, apertando Enter — como
no Code::Blocks. Não precisa preparar as respostas antes.

Enquanto o programa roda, o botão **Parar** fica ativo. Use quando ele travar ou
entrar em laço infinito.

A caixa *Entrada* é opcional: serve para deixar as respostas prontas, uma por
linha, em exercícios de entrada fixa.

> **Detalhe técnico.** Quando a saída de um programa em C vai para outro programa
> em vez de um terminal, a biblioteca do C guarda o texto num buffer e as
> perguntas só apareceriam no fim. Para evitar isso, o compilador junta ao seu
> exercício o arquivo [`ccrun/sem_buffer.c`](ccrun/sem_buffer.c), que desliga
> esse buffer antes do `main` começar. Seu código não muda em nada.

**Terminal (Shift+F5)** faz o mesmo numa janela preta separada do Windows.
Se deixar essa janela aberta e apertar F5, a compilação falha — o Windows trava
o `.exe` enquanto ele roda. A ferramenta detecta e avisa para fechar a janela.

---

## Casos de teste

Crie um arquivo com o mesmo nome do exercício e extensão `.testes`
(ex.: `01_soma.c` → `01_soma.testes`):

```
=== ENTRADA soma simples
2 3
=== SAIDA
5

=== ENTRADA com negativo
-4 10
=== SAIDA
6
```

O texto depois de `=== ENTRADA` é só o nome do caso, para você se localizar no
relatório. Aperte <kbd>F6</kbd> e ele mostra exatamente a linha que divergiu:

```
2 de 3 caso(s) passaram

✓ soma simples    (0.01s)
✓ com negativo    (0.01s)
✗ caso que falha
   entrada: 1 1
   esperado:  7
   obtido:    2
```

Formato alternativo, uma pasta com pares de arquivos:

```
testes/01_soma/01.in
testes/01_soma/01.out
```

A comparação **ignora** espaços extras e linhas em branco no final — não se perde
o exercício por um espaço a mais. Para mudar, na linha de comando existem
`--exato` e `--tolerancia 0.001` (margem para números com vírgula).

---

## O que ele detecta

**Erros de compilação traduzidos** — cerca de 30 casos comuns: ponto e vírgula
faltando (indicando que costuma estar na linha *anterior*), `scanf` sem `&`,
`#include` faltando (dizendo qual cabeçalho é), variável não declarada, chave não
fechada, `=` no lugar de `==`, formato errado no `printf`, comparação de string
com `==`, variável usada sem inicializar, função declarada mas nunca definida,
programa sem `main`, acento fora de string, cabeçalho que só existe no Linux.

**Uma revisão própria** alerta sobre armadilhas que o GCC aceita calado:

- `scanf("%s", &letra)` numa variável `char` — estouro de memória silencioso;
- `scanf("%c", ...)` sem espaço antes do `%c` — captura o Enter anterior.

**Erros de execução explicados** — em vez de um código hexadecimal:

| Sintoma | O que a ferramenta diz |
|---|---|
| Acesso inválido de memória | índice fora do vetor, ponteiro nulo, `scanf` sem `&` |
| Divisão por zero | teste o divisor antes |
| Estouro de pilha | recursão sem caso base |
| Programa não termina | laço infinito ou `scanf` esperando dado que não chega |
| Saída diferente do esperado | a linha exata da divergência, lado a lado |

Compila sempre com `-Wall -Wextra -Wshadow -Wformat=2`, que pega vários erros de
lógica antes do programa rodar, e já liga a biblioteca matemática (`-lm`) — então
`sqrt` e `pow` funcionam sem configurar nada.

---

## Linha de comando

A mesma ferramenta funciona sem a janela:

```
python cc.py rodar exercicios/01_soma.c      compila e executa
python cc.py verificar exercicios/           só compila e aponta os erros
python cc.py testar exercicios/01_soma.c     roda os casos de teste
python cc.py tudo exercicios/                placar de todos os exercícios
python cc.py novo exercicio5                 cria o .c e o arquivo de testes
python cc.py doutor                          confere o ambiente
python cc.py limpar                          apaga os executáveis gerados
```

O `tudo` dá um panorama rápido:

```
01_soma.c    OK           3/3 testes
02_media.c   NAO COMPILA  3 erro(s)
03_vetor.c   QUEBRA       compila, mas falha ao executar
04_raiz.c    OK           2/2 testes
```

---

## Exercícios de exemplo

A pasta `exercicios/` traz quatro casos, de propósito:

| Arquivo | Estado |
|---|---|
| `01_soma.c` | correto, com 3 casos de teste |
| `02_media.c` | **não compila** — falta `;` e falta `&` no `scanf` |
| `03_vetor.c` | compila mas **quebra na execução** — escreve fora do vetor |
| `04_raiz.c` | correto, usa `math.h` |

---

## Como foi feito

Python 3 e Tkinter, chamando o GCC por baixo. Sem dependências para rodar.

```
app.py                ponto de entrada da janela (vira o .exe)
cc.py                 ponto de entrada da linha de comando
ccrun/
  editor.py           a janela: editor, console e painéis
  diagnosticos.py     tradução dos erros para português
  compilar.py         chamada do GCC e escolha das flags
  executar.py         execução com limite de tempo e leitura da falha
  testes.py           leitura dos casos e comparação de saída
  toolchain.py        descoberta do compilador na máquina
  cli.py              os comandos de terminal
  cores.py            cores do terminal
  sem_buffer.c        faz as perguntas aparecerem na hora no console
instalador/           INSTALAR.bat e DESINSTALAR.bat
recursos/             ícone do programa
docs/                 a página publicada no GitHub Pages
```

### Gerando o executável

Precisa de `pyinstaller` e `pillow`:

```
pip install pyinstaller pillow
construir.bat
```

O resultado sai em `dist\Compilador-de-C.exe`.

---

## Limitações conhecidas

- Um exercício por arquivo: não há suporte a projetos com vários `.c` ligados
  entre si.
- `--sanitizar` (detector de erro de memória em tempo de execução) depende de
  bibliotecas que **não vêm** na maioria dos GCC para Windows. Quando faltam, a
  ferramenta avisa e compila sem elas.
- O tradutor cobre os erros frequentes em disciplinas de introdução. Os demais
  aparecem com a mensagem original do compilador.

---

Feito por [Matheus Raposo](https://github.com/matheusmerlim1) — Sistemas de
Informação, CEFET.
