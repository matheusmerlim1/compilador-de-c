#include <stdio.h>
#include <stdlib.h>

int main(void) {

    int tam;
    printf("Somatorio de fibonnaci \n");
    printf("informe o numero: ");
    scanf("%d", &tam);
    int *vetor = (int*)malloc(sizeof(int)*tam);
    vetor[0]=0;
    vetor[1]=1;
    int soma =0;
    
    int i= 2;
    for(i; i<tam; i++){
        vetor[i] = vetor[i-1] + vetor[i-2];
        printf("  %d  ", vetor[i]);
        if(vetor[i] %2 ==0){
            soma = soma + vetor[i];
        }
    }
    printf("\n A soma de numeros pares é: %d ",soma);
}
