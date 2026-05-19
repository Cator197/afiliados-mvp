# Extensão Chrome MinhaOferta

## Objetivo

Base inicial da extensão para gerar links com cashback no Mercado Livre.

## Como instalar para teste

1. Abrir Chrome.
2. Acessar chrome://extensions/
3. Ativar Modo do desenvolvedor.
4. Clicar em Carregar sem compactação.
5. Selecionar a pasta chrome-extension/.
6. Abrir uma página do Mercado Livre.
7. Verificar se o banner aparece apenas em página de produto.
8. Clicar no ícone da extensão e verificar o popup.

## PR 3 — Detecção de produto

Agora a extensão:

- diferencia página incompatível, Mercado Livre genérico e página de produto;
- mostra banner automático somente quando a página parece ser de produto;
- mantém verificação conservadora (em dúvida, considera não-produto);
- revalida a classificação após carregamento e em mudanças dinâmicas de URL/DOM;
- ainda não chama backend;
- ainda não gera link.

## Testes manuais

### Teste 1
Abrir google.com.

**Esperado:** popup mostra página incompatível.

### Teste 2
Abrir https://www.mercadolivre.com.br/

**Esperado:** popup mostra Mercado Livre, mas não produto.
**Esperado:** banner não aparece.

### Teste 3
Abrir uma busca no Mercado Livre.

**Esperado:** popup mostra Mercado Livre, mas não produto.
**Esperado:** banner não aparece.

### Teste 4
Abrir uma página real de produto no Mercado Livre.

**Esperado:** popup mostra produto detectado.
**Esperado:** banner aparece.

### Teste 5
Fechar o banner com X.

**Esperado:** banner é removido.
