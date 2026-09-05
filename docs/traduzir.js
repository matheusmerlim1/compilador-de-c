/*
 * Traduz as mensagens do compilador para português.
 *
 * É a versão em JavaScript das regras de ccrun/diagnosticos.py, para a página
 * online explicar os erros do mesmo jeito que o programa de computador.
 */

const LINHA_DIAG = /^(?:[^:\n]*?):(\d+):(?:(\d+):)?\s+(error|warning|fatal error|note):\s+(.*)$/;

// [padrão na mensagem original, tradução, o que fazer]
const REGRAS = [
  [/expected ['"]?\)['"]?/i,
   'Faltou fechar um parênteses ).',
   'Confira se todo ( aberto tem um ) correspondente nesta linha.'],

  [/expected .*?';'.*? before|expected ['"]?;['"]?/i,
   'Faltou um ponto e vírgula (;).',
   'O ; que falta está quase sempre no FINAL DA LINHA ANTERIOR, e não na linha apontada.'],

  [/expected ['"]?\}['"]?|expected declaration or statement at end of input/i,
   'Faltou uma chave de fechamento }.',
   'Cada { precisa de um } correspondente. Confira a indentação para achar o bloco aberto.'],

  [/use of undeclared identifier ['"](\w+)['"]|['"](\w+)['"] undeclared/i,
   "A variável ou nome '$1' não foi declarado.",
   "Declare antes de usar (ex.: int $1;) ou confira se digitou o nome errado."],

  [/implicit declaration of function ['"](\w+)['"]/i,
   "A função '$1' foi usada sem ser declarada.",
   'Provavelmente falta um #include no topo do arquivo.'],

  [/format specifies type ['"]([^'"]+)\*['"] but the argument has type ['"]([^'"]+)['"]/i,
   'No scanf, esse argumento deveria ser um endereço ($1*), mas veio $2.',
   'Faltou o & antes da variável: scanf("%d", &variavel);'],

  [/format specifies type ['"]([^'"]+)['"] but the argument has type ['"]([^'"]+)['"]/i,
   'O formato espera $1, mas recebeu $2.',
   'Use o formato certo: %d para int, %f para float/double no printf, %lf para double no scanf, %c para char, %s para string.'],

  [/too few arguments to function call|too few arguments in call/i,
   'Faltam argumentos na chamada da função.',
   'Compare a chamada com a assinatura declarada da função.'],

  [/too many arguments to function call|too many arguments in call/i,
   'Argumentos demais na chamada da função.',
   'Compare a chamada com a assinatura declarada da função.'],

  [/control (?:may )?reach(?:es)? end of non-void function/i,
   'A função promete devolver um valor mas pode terminar sem return.',
   'Garanta um return em TODOS os caminhos, inclusive dentro de if/else.'],

  [/variable ['"](\w+)['"] is uninitialized when used|['"](\w+)['"] (?:is|may be) used uninitialized/i,
   "A variável '$1' está sendo usada sem ter valor definido.",
   'Inicialize na declaração: int $1 = 0;  Ler lixo de memória gera resultado aleatório.'],

  [/unused variable ['"](\w+)['"]/i,
   "A variável '$1' foi declarada mas nunca usada.",
   'Não quebra o programa; remova a linha para deixar o código limpo.'],

  [/unused parameter ['"](\w+)['"]/i,
   "O parâmetro '$1' nunca é usado dentro da função.",
   'Não quebra o programa. Remova o parâmetro se ele não for necessário.'],

  [/comparison between pointer and integer/i,
   'Comparação entre um ponteiro e um número.',
   'Para comparar strings use strcmp(a, b) == 0 (com #include <string.h>). Para char use aspas simples: \'a\', e não "a".'],

  [/array index \d+ is past the end|array subscript .* is (?:above|below) array bounds/i,
   'Acesso fora dos limites do vetor.',
   'Índices válidos vão de 0 até tamanho-1. Reveja a condição do for.'],

  [/expression result unused|statement with no effect/i,
   'Esta instrução não faz nada.',
   'Clássico no for: escrever for(i; i<n; i++) em vez de for(i = 0; i<n; i++).'],

  [/using the result of an assignment as a condition|suggest parentheses around assignment/i,
   'Você usou = (atribuição) dentro de um if ou while.',
   'Para comparar use ==. Note que if (x = 5) sempre dá verdadeiro E ALTERA o valor de x.'],

  [/expression is not assignable|lvalue required as left operand/i,
   'O lado esquerdo do = não pode receber um valor.',
   'Erro clássico: usar = (atribuição) onde deveria ser == (comparação), ou o contrário.'],

  [/division by zero/i,
   'Divisão por zero detectada já na compilação.',
   'Verifique o divisor antes de dividir.'],

  [/missing terminating ["'] character|unterminated/i,
   'Faltou fechar as aspas.',
   'Toda string precisa abrir e fechar com aspas na MESMA linha.'],

  [/redefinition of ['"](\w+)['"]/i,
   "'$1' foi definido mais de uma vez.",
   'Remova a declaração duplicada.'],

  [/conflicting types for ['"](\w+)['"]/i,
   "A função '$1' foi declarada de duas formas diferentes.",
   'O protótipo e a definição precisam ter o mesmo tipo de retorno e os mesmos parâmetros.'],

  [/invalid operands to binary/i,
   'Os tipos usados nessa operação não combinam.',
   'Não dá para somar ou comparar diretamente tipos incompatíveis.'],

  [/character too large for enclosing character literal|multi-character character constant/i,
   'Aspas simples com mais de um caractere.',
   'Use aspas duplas para texto com mais de uma letra.'],

  [/undefined symbol: main|undefined symbol: (\w+)/i,
   "A função '$1' foi usada mas nunca foi definida.",
   'Você declarou o protótipo mas esqueceu de escrever o corpo da função, ou digitou o nome diferente na definição.'],
];

// Função usada -> cabeçalho que falta.
const INCLUDES = {
  printf: 'stdio.h', scanf: 'stdio.h', puts: 'stdio.h', gets: 'stdio.h',
  fgets: 'stdio.h', getchar: 'stdio.h', putchar: 'stdio.h', fopen: 'stdio.h',
  sprintf: 'stdio.h', fprintf: 'stdio.h', perror: 'stdio.h', fclose: 'stdio.h',
  malloc: 'stdlib.h', calloc: 'stdlib.h', realloc: 'stdlib.h', free: 'stdlib.h',
  exit: 'stdlib.h', atoi: 'stdlib.h', atof: 'stdlib.h', rand: 'stdlib.h',
  srand: 'stdlib.h', qsort: 'stdlib.h', abs: 'stdlib.h',
  strlen: 'string.h', strcpy: 'string.h', strncpy: 'string.h', strcat: 'string.h',
  strcmp: 'string.h', strncmp: 'string.h', strchr: 'string.h', strstr: 'string.h',
  memset: 'string.h', memcpy: 'string.h', strtok: 'string.h',
  sqrt: 'math.h', pow: 'math.h', fabs: 'math.h', floor: 'math.h', ceil: 'math.h',
  sin: 'math.h', cos: 'math.h', tan: 'math.h', log: 'math.h', log10: 'math.h',
  round: 'math.h', exp: 'math.h',
  toupper: 'ctype.h', tolower: 'ctype.h', isdigit: 'ctype.h', isalpha: 'ctype.h',
  isspace: 'ctype.h', isupper: 'ctype.h', islower: 'ctype.h', isalnum: 'ctype.h',
  time: 'time.h', clock: 'time.h',
  bool: 'stdbool.h', true: 'stdbool.h', false: 'stdbool.h',
};

function preencher(texto, achado) {
  // $1 vira o primeiro grupo que realmente capturou algo
  const capturado = achado.slice(1).find((g) => g !== undefined) || '';
  return texto.replace(/\$1/g, capturado)
              .replace(/\$2/g, achado[2] !== undefined ? achado[2] : '');
}

function aplicarRegras(mensagem) {
  for (const [padrao, traducao, dica] of REGRAS) {
    const achado = mensagem.match(padrao);
    if (achado) {
      return { traducao: preencher(traducao, achado), dica: preencher(dica, achado) };
    }
  }
  return { traducao: '', dica: '' };
}

function dicaDeInclude(diag) {
  const m = diag.mensagem.match(/implicit declaration of function ['"](\w+)['"]/) ||
            diag.mensagem.match(/use of undeclared identifier ['"](\w+)['"]/);
  if (!m) return;
  const cabecalho = INCLUDES[m[1]];
  if (cabecalho) {
    diag.dica = 'Adicione no topo do arquivo:  #include <' + cabecalho + '>';
  }
}

/* Lê a saída bruta do clang e devolve a lista de diagnósticos. */
function analisarSaida(bruta) {
  const diags = [];
  for (const cruaComEspaco of (bruta || '').split('\n')) {
    const crua = cruaComEspaco.replace(/\x1b\[[0-9;]*m/g, '').trim();
    const m = crua.match(LINHA_DIAG);
    if (!m) {
      const link = crua.match(/undefined symbol: (\S+)/);
      if (link) {
        const simbolo = link[1];
        const d = {
          nivel: 'error', linha: 0, coluna: 0,
          mensagem: 'undefined symbol: ' + simbolo, traducao: '', dica: '',
        };
        if (simbolo === 'main') {
          d.traducao = 'O programa não tem a função main.';
          d.dica = 'Todo programa em C precisa de:  int main(void) { ... return 0; }';
        } else {
          d.traducao = "A função '" + simbolo + "' foi usada mas nunca foi definida.";
          d.dica = 'Você declarou o protótipo mas esqueceu de escrever o corpo da função.';
        }
        diags.push(d);
      }
      continue;
    }

    const nivel = m[3];
    const mensagem = m[4].trim();
    if (nivel === 'note') {
      if (diags.length && !diags[diags.length - 1].notas.includes(mensagem)) {
        diags[diags.length - 1].notas.push(mensagem);
      }
      continue;
    }

    const d = {
      nivel,
      linha: parseInt(m[1], 10),
      coluna: m[2] ? parseInt(m[2], 10) : 0,
      mensagem,
      notas: [],
    };
    const r = aplicarRegras(mensagem);
    d.traducao = r.traducao;
    d.dica = r.dica;
    dicaDeInclude(d);
    diags.push(d);
  }
  return diags;
}

/* Revisão própria: armadilhas que o compilador aceita calado. */
function revisarFonte(codigo) {
  const linhas = codigo.split('\n');
  const texto = codigo;

  const vetores = new Set();
  let m;
  const declVetor = /\bchar\s+([A-Za-z_]\w*)\s*\[/g;
  while ((m = declVetor.exec(texto)) !== null) vetores.add(m[1]);

  const charsSimples = new Set();
  const declChar = /\bchar\s+([A-Za-z_]\w*)\s*(?:=[^;,]*)?\s*[;,]/g;
  while ((m = declChar.exec(texto)) !== null) {
    if (!vetores.has(m[1])) charsSimples.add(m[1]);
  }

  const achados = [];
  linhas.forEach((linhaCrua, i) => {
    const linha = linhaCrua.split('//')[0];
    const scanf = /\bscanf\s*\(\s*"([^"]*)"\s*,\s*([^)]*)\)/g;
    let s;
    while ((s = scanf.exec(linha)) !== null) {
      const formato = s[1];
      const nomes = s[2].split(',').map((a) => a.trim().replace(/^&/, '').trim());

      if (formato.includes('%s')) {
        for (const nome of nomes) {
          if (charsSimples.has(nome)) {
            achados.push({
              nivel: 'warning', linha: i + 1, coluna: 0, notas: [],
              mensagem: 'scanf("%s") lendo para a variável char \'' + nome + '\'',
              traducao: "'" + nome + "' guarda UMA letra, mas %s lê uma palavra inteira e ainda grava um caractere invisível de fim de texto.",
              dica: 'Para ler uma única letra troque por:  scanf(" %c", &' + nome + ');  (repare no espaço antes do %c).',
            });
          }
        }
      }
      if (formato.startsWith('%c')) {
        achados.push({
          nivel: 'warning', linha: i + 1, coluna: 0, notas: [],
          mensagem: 'scanf("%c") sem espaço antes do %c',
          traducao: 'Este %c vai capturar a tecla Enter que sobrou da leitura anterior, em vez de esperar você digitar.',
          dica: 'Escreva um espaço antes:  scanf(" %c", ...)',
        });
      }
    }
  });
  return achados;
}
