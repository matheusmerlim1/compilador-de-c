/*
 * Compilador de C online — liga o editor da página ao worker que compila.
 */

const EXEMPLOS = {
  ola: {
    nome: 'Olá, mundo',
    codigo: `#include <stdio.h>

int main(void) {

    printf("Ola, mundo!\\n");

    return 0;
}
`,
  },

  soma: {
    nome: 'Somar dois números',
    codigo: `/* Le dois numeros inteiros e imprime a soma.
   Ao rodar, uma caixa vai pedir cada valor. */
#include <stdio.h>

int main(void) {
    int a, b;

    printf("Digite o primeiro numero: ");
    scanf("%d", &a);

    printf("Digite o segundo numero: ");
    scanf("%d", &b);

    printf("A soma e: %d\\n", a + b);

    return 0;
}
`,
  },

  erro: {
    nome: 'Com erros de propósito',
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
    codigo: `/* Le um numero e imprime a raiz quadrada. */
#include <stdio.h>
#include <math.h>

int main(void) {
    double x;

    printf("Digite um numero: ");
    scanf("%lf", &x);

    printf("A raiz quadrada e: %.2f\\n", sqrt(x));

    return 0;
}
`,
  },

  menu: {
    nome: 'Menu com repetição',
    codigo: `/* Soma numeros ate voce mandar parar.
   Mostra bem a caixa de entrada aparecendo varias vezes. */
#include <stdio.h>

int main(void) {
    int soma = 0;
    int numero;
    char sair = 'n';

    while (sair != 's') {
        printf("Digite um numero: ");
        scanf("%d", &numero);
        soma = soma + numero;

        printf("Soma parcial: %d\\n", soma);
        printf("Deseja sair? (s/n): ");
        scanf(" %c", &sair);
    }

    printf("A soma total e: %d\\n", soma);

    return 0;
}
`,
  },

  fibonacci: {
    nome: 'Fibonacci — soma dos pares',
    codigo: `/* Gera a sequencia de Fibonacci e soma os numeros pares. */
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int tam;
    printf("Quantos termos? ");
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

  notas: {
    nome: 'Média de notas (vetor)',
    codigo: `/* Le quantas notas, depois cada nota, e calcula a media. */
#include <stdio.h>

int main(void) {
    int quantidade;
    float notas[100];
    float soma = 0.0f;

    printf("Quantas notas? ");
    scanf("%d", &quantidade);

    for (int i = 0; i < quantidade; i++) {
        printf("Nota %d: ", i + 1);
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
const realce = $('realce');
const saida = $('saida');
const estado = $('estado');
const btnRodar = $('rodar');
const btnParar = $('parar');
const seletor = $('exemplos');
const nomeArquivo = $('nomeArquivo');

let worker = null;
let rodando = false;

// ------------------------------------------------------------------ editor
function numerarLinhas() {
  const total = editor.value.split('\n').length;
  let txt = '';
  for (let i = 1; i <= total; i++) txt += i + '\n';
  gutter.textContent = txt;
  gutter.scrollTop = editor.scrollTop;
  realce.style.setProperty('--larguraGutter', gutter.offsetWidth + 'px');
}

function sincronizarRolagem() {
  gutter.scrollTop = editor.scrollTop;
  realce.scrollTop = editor.scrollTop;
  realce.scrollLeft = editor.scrollLeft;
}

editor.addEventListener('input', () => {
  numerarLinhas();
  marcarPar();
  const arq = arquivoAtual();
  if (arq && arq.salvo) { arq.salvo = false; desenharAbas(); }
});
editor.addEventListener('scroll', sincronizarRolagem);
editor.addEventListener('click', marcarPar);
editor.addEventListener('keyup', (e) => {
  if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) {
    marcarPar();
  }
});

/* ------------------------------------------------------------------------
 * Par de parênteses / chaves / colchetes
 *
 * Ao parar o cursor num ( { [ ) } ], acha o companheiro e pinta os dois.
 * A pintura acontece numa camada atrás do texto, porque um <textarea> não
 * aceita marcação por dentro.
 * --------------------------------------------------------------------- */
const ABRE = '([{';
const FECHA = ')]}';
const PAR = { '(': ')', '[': ']', '{': '}', ')': '(', ']': '[', '}': '{' };

function acharPar(texto, pos) {
  const ch = texto[pos];
  if (!ch) return -1;
  const alvo = PAR[ch];
  if (!alvo) return -1;

  const paraFrente = ABRE.includes(ch);
  const passo = paraFrente ? 1 : -1;
  let nivel = 0;

  for (let i = pos; i >= 0 && i < texto.length; i += passo) {
    const c = texto[i];
    if (c === ch) nivel++;
    else if (c === alvo) {
      nivel--;
      if (nivel === 0) return i;
    }
  }
  return -1;
}

function escaparHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function marcarPar() {
  const texto = editor.value;
  const cursor = editor.selectionStart;

  // considera o caractere sob o cursor e o imediatamente anterior
  let pos = -1;
  if (PAR[texto[cursor]]) pos = cursor;
  else if (cursor > 0 && PAR[texto[cursor - 1]]) pos = cursor - 1;

  if (pos === -1 || editor.selectionStart !== editor.selectionEnd) {
    realce.innerHTML = '';
    return;
  }

  const par = acharPar(texto, pos);
  if (par === -1) {
    realce.innerHTML = '';
    return;
  }

  const [a, b] = pos < par ? [pos, par] : [par, pos];
  realce.innerHTML =
    escaparHtml(texto.slice(0, a)) +
    '<mark>' + escaparHtml(texto[a]) + '</mark>' +
    escaparHtml(texto.slice(a + 1, b)) +
    '<mark>' + escaparHtml(texto[b]) + '</mark>' +
    escaparHtml(texto.slice(b + 1));
  sincronizarRolagem();
}

/* ------------------------------------------------------------------------
 * Alt + seta move a linha inteira, como no VS Code.
 * --------------------------------------------------------------------- */
function moverLinha(paraCima) {
  const texto = editor.value;
  const linhas = texto.split('\n');

  // descobre quais linhas a seleção cobre
  const antes = texto.slice(0, editor.selectionStart).split('\n');
  const primeira = antes.length - 1;
  const ate = texto.slice(0, editor.selectionEnd).split('\n');
  const ultima = ate.length - 1;

  if (paraCima && primeira === 0) return;
  if (!paraCima && ultima === linhas.length - 1) return;

  const colunaIni = antes[antes.length - 1].length;
  const colunaFim = ate[ate.length - 1].length;

  const bloco = linhas.splice(primeira, ultima - primeira + 1);
  const destino = paraCima ? primeira - 1 : primeira + 1;
  linhas.splice(destino, 0, ...bloco);

  editor.value = linhas.join('\n');

  // recoloca o cursor nas mesmas colunas, já na posição nova
  let inicio = 0;
  for (let i = 0; i < destino; i++) inicio += linhas[i].length + 1;
  const fimBloco = inicio +
    bloco.slice(0, bloco.length - 1).reduce((s, l) => s + l.length + 1, 0);

  editor.selectionStart = inicio + colunaIni;
  editor.selectionEnd = fimBloco + colunaFim;

  numerarLinhas();
  marcarPar();
}

/* Ctrl+/ comenta ou descomenta as linhas selecionadas. */
function alternarComentario() {
  const texto = editor.value;
  const linhas = texto.split('\n');
  const antes = texto.slice(0, editor.selectionStart).split('\n');
  const primeira = antes.length - 1;
  const ate = texto.slice(0, editor.selectionEnd).split('\n');
  const ultima = ate.length - 1;

  const alvo = linhas.slice(primeira, ultima + 1);
  const todasComentadas = alvo.every((l) => !l.trim() || l.trimStart().startsWith('//'));

  for (let i = primeira; i <= ultima; i++) {
    if (!linhas[i].trim()) continue;
    if (todasComentadas) {
      linhas[i] = linhas[i].replace(/^(\s*)\/\/ ?/, '$1');
    } else {
      linhas[i] = linhas[i].replace(/^(\s*)/, '$1// ');
    }
  }

  const posicao = editor.selectionStart;
  editor.value = linhas.join('\n');
  editor.selectionStart = editor.selectionEnd = Math.min(posicao, editor.value.length);
  numerarLinhas();
}

/* ------------------------------------------------------------------------
 * Ctrl+C sem nada selecionado copia a linha inteira, como no VS Code.
 * Depois o Ctrl+V cola essa linha acima da linha atual.
 * --------------------------------------------------------------------- */
let linhaCopiada = null;   // guarda a linha para o caso de o Ctrl+V não ter foco

function limitesDaLinha() {
  const texto = editor.value;
  const pos = editor.selectionStart;
  const inicio = texto.lastIndexOf('\n', pos - 1) + 1;
  let fim = texto.indexOf('\n', pos);
  if (fim === -1) fim = texto.length;
  return { inicio, fim, conteudo: texto.slice(inicio, fim) };
}

editor.addEventListener('copy', (e) => {
  if (editor.selectionStart !== editor.selectionEnd) return;  // tem seleção
  const { conteudo } = limitesDaLinha();
  linhaCopiada = conteudo + '\n';
  e.clipboardData.setData('text/plain', linhaCopiada);
  e.preventDefault();
  mostrarEstado('linha copiada', 'bom');
});

editor.addEventListener('cut', (e) => {
  if (editor.selectionStart !== editor.selectionEnd) return;
  const { inicio, fim, conteudo } = limitesDaLinha();
  linhaCopiada = conteudo + '\n';
  e.clipboardData.setData('text/plain', linhaCopiada);
  e.preventDefault();
  const texto = editor.value;
  const ateOndeApagar = fim < texto.length ? fim + 1 : fim;
  editor.value = texto.slice(0, inicio) + texto.slice(ateOndeApagar);
  editor.selectionStart = editor.selectionEnd = inicio;
  numerarLinhas();
  mostrarEstado('linha recortada', 'bom');
});

editor.addEventListener('paste', (e) => {
  const colado = (e.clipboardData || window.clipboardData).getData('text');
  // Só trata como "linha inteira" o que foi copiado como linha inteira.
  if (!colado.endsWith('\n') || editor.selectionStart !== editor.selectionEnd) return;

  e.preventDefault();
  const { inicio } = limitesDaLinha();
  const texto = editor.value;
  editor.value = texto.slice(0, inicio) + colado + texto.slice(inicio);
  const novaPos = inicio + colado.length;
  editor.selectionStart = editor.selectionEnd = novaPos;
  numerarLinhas();
  marcarPar();
});

editor.addEventListener('keydown', (e) => {
  // Alt + seta move a linha
  if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    e.preventDefault();
    moverLinha(e.key === 'ArrowUp');
    return;
  }

  // Ctrl+Shift+D duplica a linha, como no VS Code
  if (e.ctrlKey && e.shiftKey && (e.key === 'D' || e.key === 'd')) {
    e.preventDefault();
    const { inicio, fim, conteudo } = limitesDaLinha();
    const texto = editor.value;
    editor.value = texto.slice(0, fim) + '\n' + conteudo + texto.slice(fim);
    editor.selectionStart = editor.selectionEnd = fim + 1 + conteudo.length;
    numerarLinhas();
    return;
  }

  if (e.ctrlKey && (e.key === '/' || e.code === 'Slash')) {
    e.preventDefault();
    alternarComentario();
    return;
  }

  if (e.key === 'Tab') {
    e.preventDefault();
    const ini = editor.selectionStart;
    const fim = editor.selectionEnd;
    editor.value = editor.value.slice(0, ini) + '    ' + editor.value.slice(fim);
    editor.selectionStart = editor.selectionEnd = ini + 4;
    numerarLinhas();
    return;
  }

  // Enter mantém a indentação, e aumenta um nível depois de {
  if (e.key === 'Enter') {
    const ini = editor.selectionStart;
    const linhaAtual = editor.value.slice(0, ini).split('\n').pop();
    const recuo = linhaAtual.match(/^\s*/)[0];
    const extra = linhaAtual.trimEnd().endsWith('{') ? '    ' : '';
    e.preventDefault();
    const insercao = '\n' + recuo + extra;
    editor.value = editor.value.slice(0, ini) + insercao + editor.value.slice(editor.selectionEnd);
    editor.selectionStart = editor.selectionEnd = ini + insercao.length;
    numerarLinhas();
    marcarPar();
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'F5') { e.preventDefault(); rodar(); }
  if (e.key === 'Escape' && rodando && !caixaAberta()) parar();
});

/* ------------------------------------------------------------------------
 * Abas, como no VS Code
 *
 * Cada arquivo aberto é uma aba. Escolher um exemplo abre uma aba nova em
 * vez de apagar o que já estava escrito.
 * --------------------------------------------------------------------- */
const listaAbas = $('listaAbas');
const arquivos = [];      // { id, nome, codigo, salvo }
let abaAtiva = null;
let proximoId = 1;

function arquivoAtual() {
  return arquivos.find((a) => a.id === abaAtiva) || null;
}

function guardarAbaAtual() {
  const a = arquivoAtual();
  if (a) a.codigo = editor.value;
}

function desenharAbas() {
  listaAbas.innerHTML = '';
  for (const arq of arquivos) {
    const aba = document.createElement('div');
    aba.className = 'aba' + (arq.id === abaAtiva ? ' ativa' : '') +
                    (arq.salvo ? '' : ' suja');
    aba.title = arq.nome;

    const nome = document.createElement('span');
    nome.className = 'nome';
    nome.textContent = arq.nome;
    aba.appendChild(nome);

    const fechar = document.createElement('button');
    fechar.className = 'fechar';
    fechar.title = 'Fechar';
    fechar.addEventListener('click', (e) => {
      e.stopPropagation();
      fecharAba(arq.id);
    });
    aba.appendChild(fechar);

    aba.addEventListener('click', () => trocarPara(arq.id));
    listaAbas.appendChild(aba);
  }
}

function trocarPara(id) {
  if (id === abaAtiva) return;
  guardarAbaAtual();
  abaAtiva = id;
  const arq = arquivoAtual();
  if (!arq) return;
  editor.value = arq.codigo;
  nomeArquivo.value = arq.nome;
  editor.selectionStart = editor.selectionEnd = 0;
  numerarLinhas();
  marcarPar();
  desenharAbas();
}

function abrirAba(nome, codigo, ativar = true) {
  guardarAbaAtual();
  // se já existe uma aba com esse nome, abre com um número no fim
  let nomeFinal = nome;
  let n = 2;
  while (arquivos.some((a) => a.nome === nomeFinal)) {
    nomeFinal = nome.replace(/\.c$/i, '') + ' (' + n + ').c';
    n++;
  }
  const arq = { id: proximoId++, nome: nomeFinal, codigo, salvo: true };
  arquivos.push(arq);
  if (ativar) {
    abaAtiva = arq.id;
    editor.value = codigo;
    nomeArquivo.value = nomeFinal;
    numerarLinhas();
    marcarPar();
  }
  desenharAbas();
  return arq;
}

function fecharAba(id) {
  const i = arquivos.findIndex((a) => a.id === id);
  if (i === -1) return;

  if (!arquivos[i].salvo &&
      !confirm('“' + arquivos[i].nome + '” tem alterações não baixadas.\n\nFechar assim mesmo?')) {
    return;
  }

  const eraAtiva = arquivos[i].id === abaAtiva;
  arquivos.splice(i, 1);

  if (arquivos.length === 0) {
    abaAtiva = null;
    abrirAba('programa.c', EXEMPLOS.ola.codigo);
    return;
  }
  if (eraAtiva) {
    abaAtiva = null;                    // força o trocarPara a recarregar
    trocarPara(arquivos[Math.max(0, i - 1)].id);
  } else {
    desenharAbas();
  }
}

$('novaAba').addEventListener('click', () => {
  abrirAba('sem_titulo.c',
`#include <stdio.h>

int main(void) {

    return 0;
}
`);
  limparSaida();
  escrever('Arquivo novo. Escreva o código e aperte Rodar (F5).\n', 'fraco');
});

// o nome digitado na barra renomeia a aba
nomeArquivo.addEventListener('change', () => {
  const arq = arquivoAtual();
  if (!arq) return;
  let novo = nomeArquivo.value.trim() || 'programa.c';
  if (!novo.toLowerCase().endsWith('.c')) novo += '.c';
  arq.nome = novo;
  nomeArquivo.value = novo;
  desenharAbas();
});

// ---------------------------------------------------------------- exemplos
function carregarExemplo(chave) {
  const ex = EXEMPLOS[chave];
  if (!ex) return;
  abrirAba(chave + '.c', ex.codigo);
  limparSaida();
  escrever('Exemplo aberto em uma aba nova: ' + ex.nome + '.\n' +
           'Aperte Rodar (F5). O que você já tinha escrito continua nas outras abas.\n',
           'fraco');
}

const opcaoVazia = document.createElement('option');
opcaoVazia.value = '';
opcaoVazia.textContent = 'abrir exemplo…';
seletor.appendChild(opcaoVazia);
Object.entries(EXEMPLOS).forEach(([chave, ex]) => {
  const opt = document.createElement('option');
  opt.value = chave;
  opt.textContent = ex.nome;
  seletor.appendChild(opt);
});
seletor.addEventListener('change', () => {
  if (!seletor.value) return;
  carregarExemplo(seletor.value);
  seletor.value = '';        // volta para o rótulo, pronto para abrir outro
});

// ------------------------------------------------------------------ saída
function limparSaida() { saida.textContent = ''; }

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

/* ------------------------------------------------------------------------
 * A caixa que pede o valor, toda vez que o programa faz um scanf.
 * --------------------------------------------------------------------- */
const fundoCaixa = $('fundoCaixa');
const caixaPergunta = $('caixaPergunta');
const caixaValor = $('caixaValor');
let memoriaEntrada = null;   // SharedArrayBuffer combinado com o worker

function caixaAberta() { return fundoCaixa.classList.contains('aberta'); }

function abrirCaixa(pergunta) {
  caixaPergunta.textContent = pergunta || 'Digite um valor:';
  caixaValor.value = '';
  fundoCaixa.classList.add('aberta');
  mostrarEstado('esperando você digitar', 'esperando');
  setTimeout(() => caixaValor.focus(), 30);
}

function responderCaixa(texto) {
  if (!memoriaEntrada) return;
  fundoCaixa.classList.remove('aberta');

  const controle = new Int32Array(memoriaEntrada, 0, 2);
  const dados = new Uint8Array(memoriaEntrada, 8);

  if (texto === null) {
    Atomics.store(controle, 1, -1);          // -1 avisa "acabou a entrada"
  } else {
    const bytes = new TextEncoder().encode(texto.endsWith('\n') ? texto : texto + '\n');
    const quanto = Math.min(bytes.length, dados.length);
    dados.set(bytes.subarray(0, quanto));
    Atomics.store(controle, 1, quanto);
  }

  Atomics.store(controle, 0, 1);             // libera o programa
  Atomics.notify(controle, 0);
  mostrarEstado('executando', 'trabalhando');
}

$('caixaOk').addEventListener('click', () => responderCaixa(caixaValor.value));
$('caixaCancelar').addEventListener('click', () => responderCaixa(null));
caixaValor.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); responderCaixa(caixaValor.value); }
  if (e.key === 'Escape') { e.preventDefault(); responderCaixa(null); }
});

// ------------------------------------------------------------------ worker
function criarWorker() {
  worker = new Worker('worker-c.js');

  worker.onmessage = (evento) => {
    const { tipo, dados } = evento.data;

    if (tipo === 'estado' || tipo === 'progresso') {
      mostrarEstado(dados, 'trabalhando');
      return;
    }

    if (tipo === 'diagnosticos') {
      const diags = analisarSaida(dados).concat(revisarFonte(editor.value));
      if (diags.length) mostrarDiagnosticos(diags);
      else escrever('Compilou sem erros.\n\n', 'ok');
      return;
    }

    if (tipo === 'saida') {
      escrever(String(dados).replace(/\x1b\[[0-9;]*m/g, ''), 'programa');
      return;
    }

    if (tipo === 'pedirEntrada') {
      memoriaEntrada = dados.memoria;
      abrirCaixa(dados.prompt);
      return;
    }

    if (tipo === 'eco') {
      escrever(String(dados), 'digitado');
      return;
    }

    if (tipo === 'erroInterno') {
      escrever('\nErro interno: ' + dados + '\n', 'erro');
      return;
    }

    if (tipo === 'fim') {
      terminou(dados);
    }
  };

  worker.onerror = (e) => {
    escrever('\nO compilador falhou ao carregar: ' + e.message + '\n', 'erro');
    terminou({ ok: false, etapa: 'interno' });
  };

  return worker;
}

function terminou(dados) {
  rodando = false;
  btnRodar.disabled = false;
  btnParar.disabled = true;
  fundoCaixa.classList.remove('aberta');

  if (!dados) return;
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

function rodar() {
  if (rodando) return;

  if (typeof SharedArrayBuffer === 'undefined') {
    limparSaida();
    escrever('Este navegador ainda não liberou a entrada interativa.\n\n', 'erro');
    escrever('Recarregue a página (F5) — o recurso é ativado no primeiro acesso.\n' +
             'Se continuar assim, use o programa para Windows.\n', 'fraco');
    mostrarEstado('recarregue a página', 'ruim');
    return;
  }

  rodando = true;
  btnRodar.disabled = true;
  btnParar.disabled = false;
  limparSaida();
  mostrarEstado('preparando', 'trabalhando');

  if (!worker) criarWorker();
  worker.postMessage({ tipo: 'rodar', codigo: editor.value });
}

function parar() {
  if (!rodando) return;
  // O worker pode estar parado dentro de Atomics.wait; encerrar é o único
  // jeito garantido de interromper.
  if (worker) { worker.terminate(); worker = null; }
  fundoCaixa.classList.remove('aberta');
  escrever('\n■ interrompido por você\n', 'aviso');
  rodando = false;
  btnRodar.disabled = false;
  btnParar.disabled = true;
  mostrarEstado('interrompido — o compilador será recarregado', 'ruim');
}

btnRodar.addEventListener('click', rodar);
btnParar.addEventListener('click', parar);

// ------------------------------------------------------------ baixar o .c
$('baixar').addEventListener('click', () => {
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

  const arq = arquivoAtual();
  if (arq) { arq.nome = nome; arq.salvo = true; desenharAbas(); }
  mostrarEstado('arquivo ' + nome + ' baixado', 'bom');
});

// ------------------------------------------- barra que ajusta os painéis
(function ligarDivisor() {
  const divisor = $('divisor');
  const painelSaida = $('painelSaida');
  let arrastando = false;

  const mover = (y) => {
    const area = document.querySelector('main').getBoundingClientRect();
    // altura da saída = distância do ponteiro até o fim da área
    const altura = Math.max(90, Math.min(area.bottom - y, area.height - 120));
    painelSaida.style.flexBasis = altura + 'px';
  };

  divisor.addEventListener('mousedown', (e) => {
    arrastando = true;
    divisor.classList.add('arrastando');
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });
  window.addEventListener('mousemove', (e) => { if (arrastando) mover(e.clientY); });
  window.addEventListener('mouseup', () => {
    arrastando = false;
    divisor.classList.remove('arrastando');
    document.body.style.userSelect = '';
  });

  divisor.addEventListener('touchstart', (e) => { arrastando = true; e.preventDefault(); });
  window.addEventListener('touchmove', (e) => {
    if (arrastando && e.touches[0]) mover(e.touches[0].clientY);
  });
  window.addEventListener('touchend', () => { arrastando = false; });
})();

// ------------------------------------------------------------------ início
abrirAba('soma.c', EXEMPLOS.soma.codigo);
limparSaida();
escrever(
  'Escreva o código e aperte Rodar (F5).\n\n' +
  'Quando o programa pedir um dado, uma caixa vai aparecer para você digitar,\n' +
  'igual ao que acontece no terminal.\n\n' +
  'Na primeira vez, o compilador (cerca de 58 MB) é baixado para o navegador.\n' +
  'Depois disso ele fica guardado e a compilação é rápida.\n',
  'fraco');
mostrarEstado('pronto — aperte Rodar', '');
