# De onde vieram estes arquivos

`clang`, `lld`, `sysroot.tar`, `memfs` e `shared.js` são do projeto
[**wasm-clang**](https://github.com/binji/wasm-clang), de Ben Smith (binji) —
Clang/LLD compilados para WebAssembly, que permitem compilar C dentro do
navegador, sem servidor nenhum.

Licenças, mantidas junto: `LICENSE` (Apache-2.0) e `LICENSE.llvm`.

Nada aqui foi modificado. O que é nosso está em `../online.js` e
`../worker-c.js`, que usam a classe `API` do `shared.js` para compilar em C
(o projeto original compila em C++) e traduzem as mensagens do compilador
para português.
