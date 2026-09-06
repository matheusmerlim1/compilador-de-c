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

/* Mesmo arquivo de apoio do programa de computador (ccrun/apoio.c).
 *
 * Sem ele, um printf("Digite: ") sem quebra de linha ficaria preso no buffer
 * da biblioteca do C, e a pergunta só apareceria no fim — depois de a caixa
 * de entrada já ter sido mostrada, sem dizer o que o programa quer. */
const FONTE_APOIO = `/* Arquivo de apoio, compilado junto com o exercicio.
 *
 * Nada aqui muda o codigo de quem esta aprendendo: sao dois ajustes feitos
 * por fora, no momento de compilar.
 *
 *  1. Desliga o buffer da saida. Quando a saida de um programa em C vai para
 *     outro programa em vez de um terminal, a biblioteca guarda o texto e so
 *     entrega no fim — perguntas como printf("Digite: ") nao apareceriam na
 *     hora.
 *
 *  2. Avisa quando o scanf nao consegue ler o que foi pedido. Digitar uma
 *     letra onde o programa espera um numero nao da erro nenhum em C: o
 *     scanf simplesmente devolve um numero menor, a variavel fica com o
 *     valor antigo e o texto digitado CONTINUA na entrada. Dentro de um
 *     laco, isso vira repeticao infinita. O aviso torna isso visivel.
 *
 * A interceptacao do scanf usa o --wrap do ligador: as chamadas do programa
 * passam a cair em __wrap_scanf, que faz a leitura de verdade e confere o
 * resultado.
 */
#include <stdarg.h>
#include <stdio.h>

/* ------------------------------------------------------------ 1. buffer */

__attribute__((constructor))
static void cc_desliga_buffer(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}

/* ------------------------------------------------- 2. conferencia do scanf */

/* Quantos valores o formato pede: cada % que nao seja %% nem %* */
static int cc_quantos_valores(const char *formato) {
    int quantidade = 0;
    const char *p = formato;

    for (; *p; p++) {
        if (*p != '%') {
            continue;
        }
        p++;
        if (*p == '\\0') {
            break;
        }
        if (*p == '%') {      /* %% e so um sinal de porcentagem */
            continue;
        }
        if (*p == '*') {      /* %*d le e joga fora, nao guarda em variavel */
            continue;
        }
        quantidade++;
    }
    return quantidade;
}

/* A leitura de verdade, com a conferencia. As duas portas de entrada abaixo
 * chamam esta funcao:
 *
 *   __wrap_scanf        usada no computador, pelo --wrap do ligador
 *   cc_scanf_conferido  usada no navegador, por uma macro — o ligador de
 *                       WebAssembly desta versao nao conhece o --wrap
 */
static int cc_confere(const char *formato, va_list argumentos) {
    int lidos = vscanf(formato, argumentos);
    int pedidos = cc_quantos_valores(formato);

    if (lidos == EOF) {
        fflush(stdout);
        fprintf(stderr,
                "\\n[atencao] a entrada acabou e o programa ainda esperava "
                "%d valor(es).\\n", pedidos);
        fflush(stderr);
        return lidos;
    }

    if (lidos < pedidos) {
        fflush(stdout);
        fprintf(stderr,
                "\\n[atencao] o scanf pediu %d valor(es) no formato \\"%s\\", "
                "mas conseguiu ler %d.\\n"
                "          O que foi digitado nao encaixa nesse formato "
                "(por exemplo, uma letra onde se espera numero).\\n"
                "          A variavel ficou com o valor anterior, e o texto "
                "digitado continua na entrada:\\n"
                "          dentro de um laco, isso se repete sem parar.\\n",
                pedidos, formato, lidos);
        fflush(stderr);
    }

    return lidos;
}

int __wrap_scanf(const char *formato, ...) {
    va_list argumentos;
    int lidos;

    va_start(argumentos, formato);
    lidos = cc_confere(formato, argumentos);
    va_end(argumentos);
    return lidos;
}

int cc_scanf_conferido(const char *formato, ...) {
    va_list argumentos;
    int lidos;

    va_start(argumentos, formato);
    lidos = cc_confere(formato, argumentos);
    va_end(argumentos);
    return lidos;
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


/* Desvia as chamadas de scanf do exercicio para a nossa versao, que
 * confere se a leitura deu certo.
 *
 * No computador isso e feito pelo --wrap do ligador, sem tocar no
 * arquivo. Aqui nao da: o wasm-ld desta versao responde
 * "unknown argument: --wrap". Entao a macro entra antes do codigo, e o
 * #line logo depois devolve a numeracao original — sem isso, todo erro
 * apareceria uma linha adiante do lugar certo.
 */
function comConferenciaDeScanf(codigo) {
  const cabecalho =
    '#define scanf(...) cc_scanf_conferido(__VA_ARGS__)' + '\n' +
    '#line 1' + '\n';
  return cabecalho + codigo;
}

async function compilarEExecutar(codigo, entrada) {
  const api = await prepararApi();

  const fonte = 'programa.c';
  const objeto = 'programa.o';
  const wasm = 'programa.wasm';
  const fonteAux = 'apoio.c';
  const objetoAux = 'apoio.o';

  // ---------------------------------------------------------- compilação
  avisar('estado', 'compilando');
  saidaDoCompilador = '';
  capturando = true;

  let compilou = true;
  let compilouAuxiliar = true;
  let falhaDoApoio = '';
  try {
    api.memfs.addFile(fonte, comConferenciaDeScanf(codigo));
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
      api.memfs.addFile(fonteAux, FONTE_APOIO);
      const clang = await api.getModule(api.clangFilename);
      await api.run(clang, 'clang', '-cc1', '-emit-obj', ...ARGS_CLANG,
                    '-O2', '-o', objetoAux, '-x', 'c', fonteAux);
    } catch (e) {
      // Sem o apoio o programa ainda roda, so perde o aviso do scanf e a
      // saida sem buffer. Mas o motivo fica registrado.
      compilouAuxiliar = false;
      falhaDoApoio = (e && e.message) || String(e);
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
  if (falhaDoApoio) {
    avisar('progresso', 'sem o arquivo de apoio: ' + falhaDoApoio);
  }
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
