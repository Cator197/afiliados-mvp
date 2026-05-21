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

## PR 6 — Geração real via extensão

- `POST /api/extension/generate-link` cria um job real na fila atual do sistema.
- `GET /api/extension/jobs/<job_id>` permite acompanhar o status do job.
- A extensão só solicita geração após clique do usuário em “Gerar link com cashback”.
- O worker atual continua responsável por gerar o link afiliado.
- A extensão não chama worker diretamente.
- A extensão não envia cashback/comissão oficial para o backend.
- O polling da extensão é limitado (intervalo de ~2.5s, até 20 tentativas) para evitar abuso.

## PR 7 — Cashback estimado

Neste PR, o preview da extensão passou a usar estimativa calculada no backend:

- backend retorna percentual padrão configurável por `MERCADOLIVRE_DEFAULT_CASHBACK_PERCENT` (padrão `3.0`, com fallback seguro);
- extensão tenta capturar preço visível de forma leve (meta price, atributos andes e seletores comuns);
- backend normaliza o preço e calcula `estimated_cashback_value` quando válido;
- backend retorna `estimated_cashback_label` pronto para UI (valor em R$ quando houver preço, ou percentual quando não houver);
- o valor exibido é apenas estimativa visual de preview;
- cashback oficial continua dependente do fluxo atual do MinhaOferta;
- ainda não existe regra administrável por categoria/admin neste PR.

## PR 8 — Regras administráveis de cashback

O backend agora consulta regras de cashback cadastradas no banco para montar o **cashback estimado** do endpoint `POST /api/extension/product-preview`.

- Regras podem ser configuradas no admin por plataforma, `path_contains` e `category_hint_contains`.
- Existe fallback para regra default da plataforma (Mercado Livre) e fallback final por configuração.
- Essas regras valem **somente** para estimativa exibida na extensão.
- A extensão não calcula cashback oficial e não altera fluxo financeiro.
- A geração de link do PR 6 continua igual.

## PR 9 — UX, persistência e rastreabilidade

- Mensagens do popup e banner foram padronizadas para estados claros (página incompatível, não-produto, login, geração, sucesso, timeout e erro de conexão).
- Fechamento do banner agora persiste por URL (24h) com `chrome.storage.local`, sem guardar dados sensíveis.
- Navegação dinâmica no Mercado Livre passou a detectar troca de URL (`pushState`, `replaceState`, `popstate` e intervalo leve), removendo/recriando banner sem duplicação.
- Foi adicionada proteção contra múltiplos cliques durante geração no popup e no banner.
- Backend registra `source` (`site`/`extension`) em jobs e links gerados para rastreabilidade operacional.
- Admin de links ganhou visualização/filtro por origem.
- Logs simples de auditoria foram adicionados para preview, geração, rejeições e consulta de job da extensão.
- Nenhum impacto no worker, metadata_worker, confirmação de compra ou cálculo financeiro oficial de cashback.


## Popup behavior

- O popup valida a aba atual automaticamente ao abrir (sem botão manual de verificação).
- O login é validado via `GET https://minhaoferta.com/api/extension/status` com `credentials: "include"`.
- O botão **Entrar** só é exibido quando `logged_in` é `false`.

## PR 12 — Geração pelo banner

- O botão do banner agora executa geração real pelo backend da extensão somente após clique explícito do usuário.
- O banner consulta login em `GET /api/extension/status` antes de criar job.
- Quando logado, a extensão cria job com `POST /api/extension/generate-link` enviando apenas `{ "url": window.location.href }`.
- O acompanhamento do job é feito via polling limitado em `GET /api/extension/jobs/<job_id>` (~2.5s por tentativa, até 20 tentativas).
- Durante o processamento, o botão fica desabilitado e não permite múltiplos cliques/jobs concorrentes.
- Estados visuais cobertos: inicial, carregando, login necessário, sucesso, erro e timeout.
- No sucesso, o banner exibe botão único “Abrir link” e abre `affiliate_url` retornada pelo backend.
- Em timeout, o banner exibe orientação para acompanhar no MinhaOferta e botão “Abrir MinhaOferta”.
- A extensão não chama worker diretamente.
- A extensão não calcula cashback oficial e não envia percentuais/valores oficiais no payload de geração.

## PR 13 — Persistência do link gerado

- O link gerado agora é salvo em `chrome.storage.local` na chave `generatedLinks`.
- A chave de cada item é a URL normalizada do produto (`origin + pathname`, sem query string e sem hash), evitando diferenças por parâmetros de tracking/listagem.
- Estrutura persistida por produto:
  - `affiliate_url`
  - `job_id`
  - `created_at`
  - `source` (`extension`)
  - `original_url`
  - `estimated_cashback_label` (quando disponível)
  - `category_name` (quando disponível)
- Popup e banner recuperam automaticamente link salvo ao abrir/recarregar em página de produto.
- Quando existe link salvo válido, a UI prioriza estado final com botão único **“Abrir link”**.
- Se existir link salvo válido para a URL atual, a extensão não cria novo job.
- Links salvos têm validade padrão de 7 dias (`GENERATED_LINK_TTL_MS`).
- Registros expirados são removidos durante leitura/limpeza leve.
- Não são salvos dados sensíveis (sem senha, token, cookie, ou dados bancários).

### Testes manuais (PR 13)

1. Gerar link no popup e confirmar estado “Link com cashback pronto.” com botão “Abrir link”.
2. Fechar/reabrir popup na mesma página e confirmar recuperação do link salvo sem botão “Gerar link”.
3. Recarregar página do produto e confirmar que o banner reconhece o link salvo com botão “Abrir link”.
4. Abrir outro produto e confirmar que não reutiliza link do produto anterior.
5. Clicar em “Abrir link” e confirmar abertura da `affiliate_url` em nova aba.
6. Simular `created_at` antigo em `chrome.storage.local` e confirmar remoção de link expirado.
7. Inspecionar `chrome.storage.local` e confirmar ausência de senha/token/cookie/dados sensíveis.

## PR 14 — Estado final simplificado

- Após gerar o link (ou recuperar link já salvo para a URL atual), popup e banner exibem estado final simplificado com CTA único **"Abrir link"**.
- O botão **Copiar link** foi removido do estado final.
- O botão **Ver histórico** não aparece mais na área principal do estado final.
- O botão **Entrar** não aparece no estado final quando já existe `affiliate_url` válido.
- A verificação da página continua automática no popup ao abrir.
- Quando existe link salvo válido para a URL atual, a extensão mostra o estado pronto diretamente.
- Quando existe link salvo válido para a URL atual, a extensão não cria novo job.
