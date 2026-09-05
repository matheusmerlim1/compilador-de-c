/* Exercicio 3: preencher um vetor de 5 posicoes e imprimir a soma.
   ESTE ARQUIVO QUEBRA NA EXECUCAO DE PROPOSITO:
   o laco escreve muito alem do fim do vetor. */
#include <stdio.h>

int main(void) {
    int v[5];
    int soma = 0;
    int i;

    /* o erro: o vetor tem 5 posicoes (0 a 4), mas o laco vai ate 99999 */
    for (i = 0; i < 100000; i++) {
        v[i] = i;
    }

    for (i = 0; i < 5; i++) {
        soma += v[i];
    }

    printf("Soma: %d\n", soma);
    return 0;
}
