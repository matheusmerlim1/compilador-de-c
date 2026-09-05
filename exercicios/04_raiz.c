/* Exercicio 4: ler um numero e imprimir a raiz quadrada com 2 casas. */
#include <stdio.h>
#include <math.h>

int main(void) {
    double x;

    scanf("%lf", &x);
    printf("%.2f\n", sqrt(x));

    return 0;
}
