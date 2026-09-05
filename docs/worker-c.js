/*
 * Compila e roda C dentro do navegador.
 *
 * Usa a classe API do wasm-clang (Clang e LLD compilados para WebAssembly).
 * O projeto original compila C++; aqui trocamos para C (-x c) e desligamos as
 * cores e a quebra de linha das mensagens, para conseguir traduzi-las depois.
 *
 * Roda num Web Worker: compilar leva alguns segundos e travaria a página.
 */

self.importScripts('wasm/shared.js');

let api = null;
let saidaDoCompilador = '';   // guardada à parte, para ser traduzida
let capturando = false;

function avisar(tipo, dados) {
  self.postMessage({ tipo, dados });
}

const opcoes = {
  async readBuffer(nome) {
    const r = await fetch('wasm/' + nome);
    if (!r.ok) throw new Error('não consegui baixar ' + nome);
    return r.arrayBuffer();
  },

  async compileStreaming(nome) {
    const r = await fetch('wasm/' + nome);
    if (!r.ok) throw new Error('não consegui baixar ' + nome);
    return WebAssembly.compile(await r.arrayBuffer());
  },

  hostWrite(s) {
    // O wasm-clang usa uma seta amarela para o próprio progresso
    // ("> Fetching and compiling clang..."). Isso não é saída do programa
    // nem diagnóstico: vira mensagem de estado, para não sujar o painel.
    if (MARCA_PROGRESSO.test(s)) {
      const limpo = s.replace(/\x1b\[[0-9;]*m/g, '').replace(/^>\s*/, '').trim();
      if (limpo) avisar('progresso', limpo);
      return;
    }
    // Enquanto o clang roda, tudo que sai é diagnóstico; depois, é o
    // programa do usuário falando.
    if (capturando) {
      saidaDoCompilador += s;
    } else {
      ultimaSaida = (ultimaSaida + s).slice(-400);
      avisar('saida', s);
    }
  },
};

const MARCA_PROGRESSO = /\x1b\[1;93m>/;

// A classe ProcExit vive dentro do shared.js e nem sempre fica visível aqui;
// reconhecer pelo formato do erro é mais seguro do que usar instanceof.
function ehSaidaDeProcesso(e) {
  return e && typeof e.code === 'number' &&
         /process exited/i.test(String(e.message || ''));
}

/* ---------------------------------------------------------------------------
 * Entrada digitada na hora
 *
 * O scanf do C pede dados de forma síncrona: a função host_read precisa
 * devolver o texto na mesma hora, não dá para esperar uma Promise. Como este
 * código roda num Worker, dá para PARAR a thread com Atomics.wait() até a
 * página avisar que a pessoa digitou.
 *
 * A conversa acontece por uma memória compartilhada (SharedArrayBuffer):
 *   controle[0]  0 = esperando, 1 = respondido
 *   controle[1]  quantos bytes vieram
 *   dados        o texto digitado, em UTF-8
 * ------------------------------------------------------------------------- */

const TAM_ENTRADA = 64 * 1024;
let memoriaCompartilhada = null;
let controle = null;
let dados = null;

function prepararCanalDeEntrada() {
  if (memoriaCompartilhada) return true;
  if (typeof SharedArrayBuffer === 'undefined') return false;
  memoriaCompartilhada = new SharedArrayBuffer(8 + TAM_ENTRADA);
  controle = new Int32Array(memoriaCompartilhada, 0, 2);
  dados = new Uint8Array(memoriaCompartilhada, 8, TAM_ENTRADA);
  return true;
}

// Sobra do que a pessoa digitou e o programa ainda não consumiu.
let restoDaEntrada = '';
let entradaEncerrada = false;

function pedirLinhaAoUsuario(promptDoPrograma) {
  if (entradaEncerrada) return null;
  if (!prepararCanalDeEntrada()) return null;

  Atomics.store(controle, 0, 0);
  Atomics.store(controle, 1, 0);
  avisar('pedirEntrada', { memoria: memoriaCompartilhada, prompt: promptDoPrograma });

  // Para aqui até a página responder. É isto que faz o scanf esperar.
  Atomics.wait(controle, 0, 0);

  const tamanho = Atomics.load(controle, 1);
  if (tamanho < 0) {          // a pessoa cancelou: vira fim de arquivo
    entradaEncerrada = true;
    return null;
  }
  return new TextDecoder().decode(dados.slice(0, tamanho));
}

// Só pede dados enquanto o programa do usuário roda. Durante a compilação o
// clang não lê o teclado, e uma caixa aparecendo ali seria um susto.
let modoInterativo = false;

/* Faz o MemFS pedir os dados na hora, em vez de ler de uma string pronta.
 *
 * Não dá para trocar o host_read: o construtor do MemFS já amarra (bind) as
 * funções que o WebAssembly chama, e a classe nem fica visível deste arquivo.
 * Mas o host_read original consulta `this.stdinStr` a CADA leitura — então
 * basta transformar essa propriedade num getter que, quando o texto acaba,
 * para tudo e espera a pessoa digitar. O resto do host_read continua igual.
 */
function ligarEntradaInterativa(memfs) {
  let buffer = '';

  Object.defineProperty(memfs, 'stdinStr', {
    configurable: true,
    get() {
      if (!modoInterativo) return '';

      // ainda há texto não consumido desta linha
      if (this.stdinStrPos < buffer.length) return buffer;

      const linha = pedirLinhaAoUsuario(textoPendente());
      if (linha === null) {            // a pessoa encerrou: fim de arquivo
        buffer = '';
        this.stdinStrPos = 0;
        return '';
      }
      buffer = linha.endsWith('\n') ? linha : linha + '\n';
      this.stdinStrPos = 0;
      avisar('eco', buffer);           // registra na saída, como num terminal
      return buffer;
    },
    set(valor) {
      buffer = valor || '';
      this.stdinStrPos = 0;
    },
  });
}

/* O que o programa imprimiu e ainda não terminou em linha nova costuma ser a
   pergunta ("Digite um numero: "). Serve de rótulo para a caixa. */
let ultimaSaida = '';
function textoPendente() {
  const partes = ultimaSaida.split('\n');
  return partes[partes.length - 1].trim();
}

// Como o wasm-clang baixa ~58 MB, avisa o progresso para a página não parecer travada.
async function prepararApi() {
  if (api) return api;
  avisar('estado', 'baixando o compilador (isto acontece só na primeira vez)');
  api = new API(opcoes);
  ligarEntradaInterativa(api.memfs);
  await api.ready;
  avisar('estado', 'compilador pronto');
  return api;
}

const ARGS_CLANG = [
  '-disable-free',
  '-isysroot', '/',
  '-internal-isystem', '/include',
  '-internal-isystem', '/lib/clang/8.0.1/include',
  '-ferror-limit', '19',
  '-fmessage-length', '0',        // não quebra a mensagem em 80 colunas
  '-fno-color-diagnostics',       // sem códigos de cor, para dar para traduzir
  '-Wall', '-Wextra',
];

/* Mesmo auxiliar do programa de computador (ccrun/sem_buffer.c).
 *
 * Sem ele, um printf("Digite: ") sem quebra de linha ficaria preso no buffer
 * da biblioteca do C, e a pergunta só apareceria no fim — depois de a caixa
 * de entrada já ter sido mostrada, sem dizer o que o programa quer. */
const FONTE_SEM_BUFFER = `#include <stdio.h>
__attribute__((constructor))
static void cc_desliga_buffer(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}
`;

/* O link do wasm-clang aceita um objeto só; aqui precisamos de dois. */
async function ligarObjetos(api, objetos, wasm) {
  const lld = await api.getModule(api.lldFilename);
  const libdir = 'lib/wasm32-wasi';
  return api.run(
    lld, 'wasm-ld', '--no-threads', '--export-dynamic',
    '-z', 'stack-size=1048576', '-L' + libdir, libdir + '/crt1.o',
    ...objetos, '-lc', '-lc++', '-lc++abi', '-lcanvas', '-o', wasm);
}

async function compilarEExecutar(codigo, entrada) {
  const api = await prepararApi();

  const fonte = 'programa.c';
  const objeto = 'programa.o';
  const wasm = 'programa.wasm';
  const fonteAux = 'sem_buffer.c';
  const objetoAux = 'sem_buffer.o';

  // ---------------------------------------------------------- compilação
  avisar('estado', 'compilando');
  saidaDoCompilador = '';
  capturando = true;

  let compilou = true;
  let compilouAuxiliar = true;
  try {
    api.memfs.addFile(fonte, codigo);
    const clang = await api.getModule(api.clangFilename);
    await api.run(clang, 'clang', '-cc1', '-emit-obj', ...ARGS_CLANG,
                  '-O2', '-o', objeto, '-x', 'c', fonte);
  } catch (e) {
    compilou = false;
    // Erro de compilação chega como saída de processo com código != 0. Nesse
    // caso o texto útil já está nos diagnósticos, não precisa repetir.
    if (!ehSaidaDeProcesso(e)) {
      saidaDoCompilador += '\n' + (e.message || String(e));
    }
  }

  // O auxiliar é nosso e não pode falhar por causa do código do usuário;
  // compila em separado, sem capturar diagnóstico dele.
  if (compilou) {
    try {
      api.memfs.addFile(fonteAux, FONTE_SEM_BUFFER);
      const clang = await api.getModule(api.clangFilename);
      await api.run(clang, 'clang', '-cc1', '-emit-obj', ...ARGS_CLANG,
                    '-O2', '-o', objetoAux, '-x', 'c', fonteAux);
    } catch (e) {
      // se o auxiliar falhar, segue sem ele: o programa ainda roda
      compilouAuxiliar = false;
    }
  }

  // ------------------------------------------------------------- ligação
  if (compilou) {
    try {
      const objetos = compilouAuxiliar ? [objeto, objetoAux] : [objeto];
      await ligarObjetos(api, objetos, wasm);
    } catch (e) {
      compilou = false;
      if (!ehSaidaDeProcesso(e)) {
        saidaDoCompilador += '\n' + (e.message || String(e));
      }
    }
  }

  capturando = false;
  avisar('diagnosticos', saidaDoCompilador);

  if (!compilou) {
    avisar('fim', { ok: false, etapa: 'compilacao' });
    return;
  }

  // ------------------------------------------------------------ execução
  avisar('estado', 'executando');
  restoDaEntrada = '';
  entradaEncerrada = false;
  ultimaSaida = '';
  modoInterativo = true;

  let codigoSaida = 0;
  try {
    const binario = api.memfs.getFileContents(wasm);
    const modulo = await WebAssembly.compile(binario);
    await api.run(modulo, wasm);
  } catch (e) {
    if (ehSaidaDeProcesso(e)) {
      codigoSaida = e.code;
    } else {
      avisar('saida', '\n' + (e.message || String(e)) + '\n');
      codigoSaida = -1;
    }
  }
  modoInterativo = false;
  avisar('fim', { ok: codigoSaida === 0, etapa: 'execucao', codigo: codigoSaida });
}

self.onmessage = async (evento) => {
  const { tipo, codigo, entrada } = evento.data;
  if (tipo !== 'rodar') return;
  try {
    await compilarEExecutar(codigo, entrada);
  } catch (e) {
    avisar('erroInterno', e.message || String(e));
    avisar('fim', { ok: false, etapa: 'interno' });
  }
};
