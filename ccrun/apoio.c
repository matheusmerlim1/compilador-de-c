/* Arquivo de apoio, compilado junto com o exercicio.
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
        if (*p == '\0') {
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
                "\n[atencao] a entrada acabou e o programa ainda esperava "
                "%d valor(es).\n", pedidos);
        fflush(stderr);
        return lidos;
    }

    if (lidos < pedidos) {
        fflush(stdout);
        fprintf(stderr,
                "\n[atencao] o scanf pediu %d valor(es) no formato \"%s\", "
                "mas conseguiu ler %d.\n"
                "          O que foi digitado nao encaixa nesse formato "
                "(por exemplo, uma letra onde se espera numero).\n"
                "          A variavel ficou com o valor anterior, e o texto "
                "digitado continua na entrada:\n"
                "          dentro de um laco, isso se repete sem parar.\n",
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
