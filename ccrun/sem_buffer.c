/* Auxiliar compilado junto com o exercicio quando ele roda no console da janela.
 *
 * Quando a saida do programa vai para um "cano" (pipe) em vez de um terminal,
 * a biblioteca do C guarda o texto em um buffer e so entrega no fim. O efeito
 * e que perguntas como printf("Digite um numero") nao aparecem na hora.
 *
 * O atributo constructor faz esta funcao rodar ANTES do main, desligando o
 * buffer. Assim cada printf chega na tela imediatamente, como em um terminal.
 * Nada no codigo do exercicio precisa mudar.
 */
#include <stdio.h>

__attribute__((constructor))
static void cc_desliga_buffer(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}
