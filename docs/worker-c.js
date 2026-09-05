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

// Como o wasm-clang baixa ~58 MB, avisa o progresso para a página não parecer travada.
async function prepararApi() {
  if (api) return api;
  avisar('estado', 'baixando o compilador (isto acontece só na primeira vez)');
  api = new API(opcoes);
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

async function compilarEExecutar(codigo, entrada) {
  const api = await prepararApi();

  const fonte = 'programa.c';
  const objeto = 'programa.o';
  const wasm = 'programa.wasm';

  // ---------------------------------------------------------- compilação
  avisar('estado', 'compilando');
  saidaDoCompilador = '';
  capturando = true;

  let compilou = true;
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

  // ------------------------------------------------------------- ligação
  if (compilou) {
    try {
      await api.link(objeto, wasm);
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
  api.memfs.setStdinStr(entrada || '');

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
