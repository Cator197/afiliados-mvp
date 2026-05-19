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

## PR 4 — Fluxo visual de geração

Neste PR, a extensão evolui a UX local para o fluxo de geração de link, **sem backend**:

- o botão “Gerar link com cashback” aparece no banner e no popup;
- ao clicar, a extensão entra em estado de carregamento simulado (1 a 2 segundos);
- após o carregamento, mostra estado de sucesso simulado;
- o popup exibe ações de abrir MinhaOferta e copiar link simulado;
- ainda não existe chamada ao backend;
- ainda não existe job real;
- ainda não existe geração de link real.

## Testes manuais

### Teste 1 — Página incompatível
1. Abrir google.com.
2. Clicar no ícone da extensão.
3. Confirmar mensagem de página incompatível.

### Teste 2 — Mercado Livre não produto
1. Abrir a home ou busca do Mercado Livre.
2. Confirmar que o banner não aparece.
3. Confirmar que o popup informa que não parece produto.

### Teste 3 — Produto Mercado Livre
1. Abrir página real de produto.
2. Confirmar que o banner aparece.
3. Confirmar que o botão “Gerar link com cashback” aparece.

### Teste 4 — Fluxo simulado no banner
1. Clicar em “Gerar link com cashback”.
2. Confirmar estado carregando.
3. Confirmar estado sucesso simulado.
4. Clicar em “Abrir MinhaOferta”.
5. Confirmar abertura de https://minhaoferta.com.

### Teste 5 — Fluxo simulado no popup
1. Abrir produto Mercado Livre.
2. Clicar no ícone da extensão.
3. Clicar em “Gerar link com cashback”.
4. Confirmar estado carregando.
5. Confirmar sucesso simulado.

## PR 5 — Endpoints de status e preview

Este PR adiciona endpoints backend para a extensão:

- `GET /api/extension/status`: verifica se existe sessão ativa de usuário no MinhaOferta.
- `POST /api/extension/product-preview`: valida URL enviada pela extensão e retorna preview leve.

Escopo atual:

- ainda não há geração real de link;
- ainda não há criação de job;
- ainda não há chamada de worker;
- cashback retornado é apenas estimado e provisório (preview visual).

### Exemplos com curl

Teste status:

```bash
curl -i https://minhaoferta.com/api/extension/status
```

Teste preview URL inválida:

```bash
curl -i -X POST https://minhaoferta.com/api/extension/product-preview \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://google.com\"}"
```

Teste preview Mercado Livre home:

```bash
curl -i -X POST https://minhaoferta.com/api/extension/product-preview \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://www.mercadolivre.com.br\"}"
```

Teste preview produto Mercado Livre:

```bash
curl -i -X POST https://minhaoferta.com/api/extension/product-preview \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"COLE_AQUI_UMA_URL_REAL_DE_PRODUTO\"}"
```
