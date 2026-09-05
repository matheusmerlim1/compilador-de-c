/*
 * Compilador de C online — liga o editor da página ao worker que compila.
 */

const EXEMPLOS = {
  ola: {
    nome: 'Olá, mundo',
    entrada: '',
    codigo: `#include <stdio.h>

int main(void) {

    printf("Ola, mundo!\\n");

    return 0;
}
`,
  },

  soma: {
    nome: 'Somar dois números',
    entrada: '7 5',
    codigo: `/* Le dois numeros inteiros e imprime a soma.
   A entrada esta na caixa ao lado. */
#include <stdio.h>

int main(void) {
    int a, b;

    scanf("%d %d", &a, &b);
    printf("%d\\n", a + b);

    return 0;
}
`,
  },

  erro: {
    nome: 'Com erros de propósito',
    entrada: '8 7 9',
    codigo: `/* Este exemplo NAO compila, de proposito.
   Aperte Rodar para ver os erros explicados em portugues. */
#include <stdio.h>

int main(void) {
    float n1, n2, n3
    float media;

    scanf("%f %f %f", n1, &n2, &n3);

    media = (n1 + n2 + n3) / 3;
    printf("Media: %.2f\\n", media);

    return 0;
}
`,
  },

  raiz: {
    nome: 'Raiz quadrada (math.h)',
    entrada: '16',
    codigo: `/* Le um numero e imprime a raiz quadrada. */
#include <stdio.h>
#include <math.h>

int main(void) {
    double x;

    scanf("%lf", &x);
    printf("%.2f\\n", sqrt(x));

    return 0;
}
`,
  },

  fibonacci: {
    nome: 'Fibonacci — soma dos pares',
    entrada: '10',
    codigo: `/* Gera a sequencia de Fibonacci e soma os numeros pares. */
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int tam;
    printf("Somatorio de fibonacci \\n");
    printf("informe o numero: ");
    scanf("%d", &tam);

    int *vetor = (int*) malloc(sizeof(int) * tam);
    vetor[0] = 0;
    vetor[1] = 1;
    int soma = 0;

    for (int i = 2; i < tam; i++) {
        vetor[i] = vetor[i-1] + vetor[i-2];
        printf("  %d  ", vetor[i]);
        if (vetor[i] % 2 == 0) {
            soma = soma + vetor[i];
        }
    }

    printf("\\n A soma de numeros pares e: %d\\n", soma);

    free(vetor);
    return 0;
}
`,
  },

  vetor: {
    nome: 'Média de um vetor',
    entrada: '5\n10 8 7 9 6',
    codigo: `/* Le quantas notas, depois as notas, e calcula a media. */
#include <stdio.h>

int main(void) {
    int quantidade;
    float notas[100];
    float soma = 0.0f;

    scanf("%d", &quantidade);

    for (int i = 0; i < quantidade; i++) {
        scanf("%f", &notas[i]);
        soma = soma + notas[i];
    }

    printf("Media: %.2f\\n", soma / quantidade);

    return 0;
}
`,
  },
};

// ---------------------------------------------------------------- elementos
const $ = (id) => document.getElementById(id);
const editor = $('editor');
const gutter = $('gutter');
const entrada = $('entrada');
const saida = $('saida');
const estado = $('estado');
const btnRodar = $('rodar');
const btnBaixar = $('baixar');
const seletor = $('exemplos');
const nomeArquivo = $('nomeArquivo');

let worker = null;
let rodando = false;
let houveErroDeCompilacao = false;

// ------------------------------------------------------------------ editor
function numerarLinhas() {
  const total = editor.value.split('\n').length;
  let txt = '';
  for (let i = 1; i <= total; i++) txt += i + '\n';
  gutter.textContent = txt;
  gutter.scrollTop = editor.scrollTop;
}

editor.addEventListener('input', numerarLinhas);
editor.addEventListener('scroll', () => { gutter.scrollTop = editor.scrollTop; });

// Tab escreve 4 espaços em vez de pular de campo.
editor.addEventListener('keydown', (e) => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const ini = editor.selectionStart;
    const fim = editor.selectionEnd;
    editor.value = editor.value.slice(0, ini) + '    ' + editor.value.slice(fim);
    editor.selectionStart = editor.selectionEnd = ini + 4;
    numerarLinhas();
  }
  if (e.key === 'F5' || (e.ctrlKey && e.key === 'Enter')) {
    e.preventDefault();
    rodar();
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'F5') { e.preventDefault(); rodar(); }
});

// ---------------------------------------------------------------- exemplos
function carregarExemplo(chave) {
  const ex = EXEMPLOS[chave];
  if (!ex) return;
  editor.value = ex.codigo;
  entrada.value = ex.entrada;
  nomeArquivo.value = chave + '.c';
  numerarLinhas();
  limparSaida();
  escrever('Exemplo carregado: ' + ex.nome + '. Aperte Rodar (F5).', 'fraco');
}

Object.entries(EXEMPLOS).forEach(([chave, ex]) => {
  const opt = document.createElement('option');
  opt.value = chave;
  opt.textContent = ex.nome;
  seletor.appendChild(opt);
});
seletor.addEventListener('change', () => carregarExemplo(seletor.value));

// ------------------------------------------------------------------ saída
function limparSaida() {
  saida.textContent = '';
}

function escrever(texto, classe) {
  const span = document.createElement('span');
  if (classe) span.className = classe;
  span.textContent = texto;
  saida.appendChild(span);
  saida.scrollTop = saida.scrollHeight;
}

function mostrarEstado(texto, classe) {
  estado.textContent = texto;
  estado.className = 'estado ' + (classe || '');
}

function linhaDoCodigo(n) {
  const linhas = editor.value.split('\n');
  return (n >= 1 && n <= linhas.length) ? linhas[n - 1] : '';
}

function mostrarDiagnosticos(diags) {
  for (const d of diags) {
    const eErro = d.nivel === 'error' || d.nivel === 'fatal error';
    escrever(eErro ? 'ERRO' : 'AVISO', eErro ? 'erro' : 'aviso');
    escrever(d.linha ? '  linha ' + d.linha + '\n' : '  ligação\n', 'negrito');

    escrever('   ' + (d.traducao || d.mensagem) + '\n');
    if (d.traducao) escrever('   original: ' + d.mensagem + '\n', 'fraco');

    if (d.linha) {
      const trecho = linhaDoCodigo(d.linha);
      if (trecho.trim()) {
        escrever('   ' + String(d.linha).padStart(4) + ' | ' + trecho.trim() + '\n', 'codigo');
      }
    }
    if (d.dica) escrever('   como corrigir: ' + d.dica + '\n', 'dica');
    for (const nota of (d.notas || []).slice(0, 2)) {
      escrever('   nota: ' + nota + '\n', 'fraco');
    }
    escrever('\n');
  }
}

// ------------------------------------------------------------------ worker
function garantirWorker() {
  if (worker) return worker;
  worker = new Worker('worker-c.js');

  worker.onmessage = (evento) => {
    const { tipo, dados } = evento.data;

    if (tipo === 'estado' || tipo === 'progresso') {
      mostrarEstado(dados, 'trabalhando');
      return;
    }

    if (tipo === 'diagnosticos') {
      const diags = analisarSaida(dados).concat(revisarFonte(editor.value));
      houveErroDeCompilacao = diags.some(
        (d) => d.nivel === 'error' || d.nivel === 'fatal error');
      if (diags.length) mostrarDiagnosticos(diags);
      else if (!houveErroDeCompilacao) escrever('Compilou sem erros.\n\n', 'ok');
      return;
    }

    if (tipo === 'saida') {
      // o clang pode mandar códigos de cor; tira antes de mostrar
      escrever(String(dados).replace(/\x1b\[[0-9;]*m/g, ''), 'programa');
      return;
    }

    if (tipo === 'erroInterno') {
      escrever('\nErro interno: ' + dados + '\n', 'erro');
      return;
    }

    if (tipo === 'fim') {
      rodando = false;
      btnRodar.disabled = false;
      btnRodar.textContent = '▶  Rodar   (F5)';

      if (dados.etapa === 'compilacao') {
        mostrarEstado('não compilou', 'ruim');
      } else if (dados.ok) {
        escrever('\n✓ o programa terminou normalmente\n', 'ok');
        mostrarEstado('executou sem erros', 'bom');
      } else if (dados.etapa === 'execucao') {
        escrever('\n✗ o programa terminou com código ' + dados.codigo + '\n', 'erro');
        mostrarEstado('terminou com erro', 'ruim');
      } else {
        mostrarEstado('falhou', 'ruim');
      }
    }
  };

  worker.onerror = (e) => {
    escrever('\nO compilador falhou ao carregar: ' + e.message + '\n', 'erro');
    mostrarEstado('falhou', 'ruim');
    rodando = false;
    btnRodar.disabled = false;
    btnRodar.textContent = '▶  Rodar   (F5)';
  };

  return worker;
}

function rodar() {
  if (rodando) return;
  rodando = true;
  houveErroDeCompilacao = false;
  btnRodar.disabled = true;
  btnRodar.textContent = 'compilando...';
  limparSaida();
  mostrarEstado('preparando', 'trabalhando');

  garantirWorker().postMessage({
    tipo: 'rodar',
    codigo: editor.value,
    entrada: entrada.value.endsWith('\n') ? entrada.value : entrada.value + '\n',
  });
}

btnRodar.addEventListener('click', rodar);

// ------------------------------------------------------------ baixar o .c
btnBaixar.addEventListener('click', () => {
  let nome = (nomeArquivo.value || 'programa.c').trim();
  if (!nome.toLowerCase().endsWith('.c')) nome += '.c';

  const blob = new Blob([editor.value], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);

  mostrarEstado('arquivo ' + nome + ' baixado', 'bom');
});

// ------------------------------------------------------------------ início
carregarExemplo('soma');
seletor.value = 'soma';
mostrarEstado('pronto — aperte Rodar', '');
limparSaida();
escrever(
  'Na primeira vez que você apertar Rodar, o compilador (cerca de 58 MB) será\n' +
  'baixado para o seu navegador. Isso leva um tempo. Nas vezes seguintes ele\n' +
  'já fica guardado e a compilação é rápida.\n',
  'fraco');
