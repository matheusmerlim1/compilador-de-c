/* Incluido antes do exercicio (gcc -include), so no Windows.
 *
 * Os exemplos de Programacao Paralela sao escritos no Linux e usam
 * funcoes POSIX que a biblioteca C do Windows nao tem. Aqui ficam so as
 * declaracoes; o corpo esta em apoio.c, marcado como "fraco": se o
 * exercicio tiver a sua propria versao, vale a dele.
 */
#ifndef CC_COMPAT_POSIX_H
#define CC_COMPAT_POSIX_H

#ifdef _WIN32
int rand_r(unsigned int *semente);
#endif

#endif
