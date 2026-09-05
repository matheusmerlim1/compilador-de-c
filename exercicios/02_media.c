/* Exercicio 2: ler 3 notas e imprimir a media com 2 casas decimais.
   ESTE ARQUIVO TEM ERROS DE PROPOSITO - serve para ver o relatorio da ferramenta. */
#include <stdio.h>

int main(void) {
    float n1, n2, n3
    float media;

    scanf("%f %f %f", n1, &n2, &n3);

    media = (n1 + n2 + n3) / 3;
    printf("Media: %.2f\n", media);

    return 0;
}
