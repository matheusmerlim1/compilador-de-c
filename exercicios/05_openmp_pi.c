/* Aproximacao de PI com OpenMP (soma de retangulos de 4/(1+x^2) entre 0 e 1).
 *
 * O compilador liga o -fopenmp sozinho ao ver o #pragma omp, como nos
 * Makefiles da disciplina de Programacao Paralela. A barra de baixo mostra
 * "OpenMP ligado". O reduction(+:soma) da a cada thread a sua propria soma
 * parcial e junta tudo no fim; sem ele, as threads disputariam a variavel e
 * o resultado sairia errado.
 */
#include <stdio.h>
#include <omp.h>

int main(void) {
    const long passos = 20000000;
    const double largura = 1.0 / (double)passos;
    double soma = 0.0;

    double inicio = omp_get_wtime();

    #pragma omp parallel for reduction(+:soma)
    for (long i = 0; i < passos; i++) {
        double x = (i + 0.5) * largura;
        soma += 4.0 / (1.0 + x * x);
    }

    double tempo = omp_get_wtime() - inicio;

    printf("PI = %.6f\n", soma * largura);
    fprintf(stderr, "threads: %d   tempo: %.3f s\n", omp_get_max_threads(), tempo);
    return 0;
}
