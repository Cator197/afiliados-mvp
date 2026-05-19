# PR 1 — Documentação inicial da Extensão Chrome MinhaOferta

## 1. Objetivo da extensão

A extensão Chrome MinhaOferta terá como objetivo facilitar a geração de links com cashback diretamente durante a navegação do usuário no Mercado Livre.

O usuário não precisará copiar manualmente o link do produto, abrir o site MinhaOferta, colar o link e aguardar a geração. A extensão deverá detectar a página atual, validar se é um produto do Mercado Livre e oferecer uma ação direta para gerar o link com cashback.

## 2. Fluxo ideal desejado

Fluxo futuro previsto:

1. Usuário acessa uma página de produto do Mercado Livre.
2. A extensão detecta automaticamente que a página é compatível.
3. Um aviso discreto é exibido na própria página, por exemplo:
   “Gere o link para receber cashback”.
4. O usuário clica no botão.
5. A extensão verifica se o usuário está logado no MinhaOferta.
6. Se não estiver logado, abre a página de login em nova aba.
7. Se estiver logado, envia a URL atual para o backend.
8. O backend valida a URL.
9. O backend cria um job de geração de link.
10. O worker atual gera o link afiliado.
11. A extensão consulta o status do job.
12. Quando o link estiver pronto, a extensão exibe o resultado para o usuário.
13. O usuário pode copiar o link ou abrir o histórico.

## 3. Decisão de UX/UI

A experiência ideal não deve depender apenas do usuário clicar no ícone da extensão.

A extensão deve ter dois pontos de interação:

### 3.1 Banner automático na página

Um pequeno aviso discreto dentro da página do Mercado Livre.

Exemplo:

“MinhaOferta — Gere o link para receber cashback”

Características desejadas:
- discreto;
- não invasivo;
- fácil de fechar;
- não cobrir o botão de compra;
- não atrapalhar a navegação;
- não parecer anúncio agressivo;
- manter aparência confiável.

### 3.2 Popup da extensão

Ao clicar no ícone da extensão, o usuário deve ver um popup simples com:
- status da página atual;
- cashback estimado, quando disponível;
- botão para gerar link;
- botão para abrir login;
- botão para abrir histórico;
- resultado do link gerado;
- botão para copiar link.

## 4. Arquitetura técnica futura

A extensão deve ficar em uma pasta própria dentro do repositório:

chrome-extension/

Estrutura futura sugerida:

chrome-extension/
├── manifest.json
├── popup.html
├── popup.js
├── content.js
├── background.js
├── styles.css
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png

## 5. Responsabilidade de cada arquivo futuro

### manifest.json

Arquivo obrigatório da extensão Chrome.

Deve definir:
- nome da extensão;
- versão;
- permissões;
- host_permissions;
- popup padrão;
- content scripts;
- background service worker, se necessário;
- ícones.

A extensão deve usar Manifest V3.

### popup.html

Interface exibida quando o usuário clicar no ícone da extensão.

### popup.js

Lógica do popup:
- capturar aba atual;
- validar URL;
- chamar backend;
- mostrar status;
- abrir login/histórico;
- copiar link gerado.

### content.js

Script executado dentro das páginas do Mercado Livre.

Responsável por:
- detectar páginas de produto;
- inserir o aviso automático na página;
- capturar URL, preço, título ou categoria, se necessário;
- enviar ação para gerar link.

### background.js

Arquivo opcional para centralizar:
- comunicação entre content script e popup;
- chamadas ao backend;
- controle de estado;
- mensagens internas da extensão.

### styles.css

Estilos do popup e do banner automático inserido na página.

## 6. Backend atual que será reaproveitado

A extensão não deve gerar link diretamente.

Ela deverá usar o backend atual do MinhaOferta.

Partes que devem ser reaproveitadas futuramente:
- validação de URL;
- criação de jobs;
- consulta de status do job;
- autenticação do usuário;
- histórico de links;
- worker atual de geração de link.

O worker não deve ser chamado diretamente pela extensão.

Fluxo correto:

Extensão → Backend Flask → Banco/jobs → Worker → Backend → Extensão

## 7. Worker

O worker atual deve ser reaproveitado.

A extensão apenas criará uma nova origem de job.

Futuramente pode ser útil adicionar um campo no job ou no link gerado, como:

source = "extension"

ou

origem = "extensao_chrome"

Isso permitirá:
- filtrar links gerados pela extensão no admin;
- medir uso da extensão;
- auditar problemas;
- separar métricas de site e extensão.

## 8. Cashback estimado

O cashback estimado não deve ser definido de forma oficial pela extensão.

A extensão pode capturar:
- URL;
- preço visível;
- título;
- categoria aproximada.

Mas o cálculo oficial deve ser feito ou validado pelo backend.

Motivo:
O código da extensão roda no navegador do usuário e pode ser alterado. Portanto, o frontend nunca deve ser fonte confiável para valor de cashback, percentual, comissão ou confirmação de compra.

Regra obrigatória:
A extensão pode exibir estimativa, mas o backend é a fonte da verdade.

## 9. Estratégia de cashback por categoria

Existem algumas opções futuras:

### Opção A — Regra padrão por plataforma

Exemplo:
Todo produto Mercado Livre mostra cashback estimado padrão.

Vantagens:
- simples;
- rápido para MVP;
- baixo risco;
- não depende de scraping da categoria.

Desvantagens:
- menos preciso.

### Opção B — Categoria pelo path da URL

A extensão ou backend tenta identificar a categoria pela URL.

Vantagens:
- leve;
- rápido;
- não depende tanto do HTML.

Desvantagens:
- nem toda URL tem categoria clara;
- pode ter inconsistências.

### Opção C — Categoria pelo HTML da página

O content.js tenta capturar breadcrumbs, metadados ou elementos da página.

Vantagens:
- pode ser mais preciso;
- permite mostrar cashback estimado no próprio banner.

Desvantagens:
- depende da estrutura do Mercado Livre;
- pode quebrar quando o site mudar.

### Opção D — Backend/metadata_worker identifica categoria

A URL é enviada ao backend, que identifica a categoria.

Vantagens:
- mais centralizado;
- regra fica no servidor.

Desvantagens:
- pode ser mais pesado;
- pode depender de scraping;
- não é ideal para preview rápido.

### Opção E — Tabela administrável de regras

Criar futuramente uma tabela no admin com:
- plataforma;
- categoria;
- path ou identificador;
- percentual estimado;
- status ativo/inativo.

Vantagens:
- escalável;
- editável sem atualizar extensão;
- melhor controle operacional.

Desvantagens:
- exige desenvolvimento adicional.

Recomendação para MVP:
Começar com regra padrão de cashback para Mercado Livre retornada pelo backend.
Depois evoluir para regras por categoria/path.

## 10. Endpoints futuros sugeridos

Este PR não deve criar endpoints.

Mas a arquitetura futura pode usar:

### GET /api/extension/status

Objetivo:
Verificar se o usuário está logado.

Retorno esperado:
- logged_in;
- nome do usuário;
- código do usuário;
- URLs úteis para login e histórico.

### POST /api/extension/product-preview

Objetivo:
Receber a URL atual e retornar se a página é compatível.

Pode retornar:
- is_valid_product;
- platform;
- estimated_cashback_percent;
- estimated_cashback_value;
- message;
- login_required.

Esse endpoint não deve criar job e não deve chamar worker.

### POST /api/extension/generate-link

Objetivo:
Criar o job de geração de link a partir da URL enviada pela extensão.

Deve:
- exigir usuário autenticado;
- validar URL;
- criar job;
- retornar job_id;
- não aceitar cashback calculado pelo frontend como verdade.

### GET /api/extension/jobs/<job_id>

Objetivo:
Consultar status do job criado pela extensão.

Deve:
- exigir autenticação;
- garantir que o job pertence ao usuário logado;
- retornar status, mensagem e link final, se disponível.

## 11. Segurança

Pontos importantes para desenvolvimento futuro:

- A extensão não deve armazenar senha.
- A extensão não deve conter token do worker.
- A extensão não deve ter acesso ao admin.
- A extensão não deve enviar cashback oficial.
- O backend deve validar o domínio.
- O backend deve validar se a URL é realmente do Mercado Livre.
- O backend deve impedir subdomain spoofing.
- O backend deve exigir autenticação para gerar link.
- O backend deve impedir usuário A de consultar job do usuário B.
- O backend deve ter rate limit para evitar abuso.
- O backend deve registrar logs de geração via extensão.
- O backend deve considerar CSRF, CORS, Origin e cookies.
- O backend deve ser a fonte da verdade para cashback.

## 12. UX recomendada

Estados principais:

### Página compatível

Mensagem:
“Cashback disponível neste produto.”

Botão:
“Gerar link com cashback”

### Página incompatível

Mensagem:
“Esta página não parece ser um produto do Mercado Livre.”

### Usuário não logado

Mensagem:
“Entre no MinhaOferta para gerar seu link com cashback.”

Botão:
“Entrar”

### Gerando link

Mensagem:
“Gerando seu link com cashback...”

### Link pronto

Mensagem:
“Link gerado com sucesso.”

Ações:
- copiar link;
- abrir histórico.

### Erro

Mensagem:
“Não foi possível gerar o link agora. Tente novamente.”

## 13. Forma de instalação para teste

Durante o desenvolvimento, a extensão será instalada manualmente:

1. Abrir Chrome.
2. Acessar chrome://extensions/
3. Ativar “Modo do desenvolvedor”.
4. Clicar em “Carregar sem compactação”.
5. Selecionar a pasta chrome-extension/.
6. Testar localmente.
7. Após alterações, clicar em “Atualizar” na extensão.

## 14. Forma de publicação futura

Quando estiver estável, a extensão poderá ser publicada na Chrome Web Store.

Opções:
- não listada, para beta fechado;
- pública, para todos os usuários.

Será necessário preparar:
- ZIP da extensão;
- ícones;
- descrição;
- imagens;
- política de privacidade;
- justificativa das permissões;
- versão;
- conta no Chrome Developer Dashboard.

## 15. Plano de PRs futuros

### PR 2 — Criar base da extensão

Criar pasta chrome-extension/ com:
- manifest.json;
- popup.html;
- popup.js;
- content.js;
- styles.css;
- ícones provisórios.

Sem integração com backend.

### PR 3 — Detectar página Mercado Livre

Implementar:
- captura da URL atual;
- validação de domínio;
- mensagem de página compatível/incompatível no popup.

### PR 4 — Banner automático na página

Implementar content.js para mostrar aviso discreto no Mercado Livre.

Sem gerar link ainda.

### PR 5 — Endpoints de status e preview

Criar:
- GET /api/extension/status;
- POST /api/extension/product-preview.

Sem chamar worker.

### PR 6 — Endpoint de geração via extensão

Criar:
- POST /api/extension/generate-link.

Reaproveitar fluxo atual de criação de job.

### PR 7 — Consulta de status do job

Criar:
- GET /api/extension/jobs/<job_id>.

Garantir isolamento por usuário.

### PR 8 — Integração da extensão com backend

Conectar botão do banner/popup ao backend.

### PR 9 — Cashback estimado

Adicionar cálculo inicial com regra padrão no backend.

### PR 10 — Regras administráveis de cashback

Criar tabela e admin para regras por plataforma/categoria/path.

### PR 11 — Segurança e hardening

Adicionar:
- rate limit;
- logs;
- validação de Origin/CORS;
- testes de abuso;
- testes de isolamento entre usuários.

## 16. Decisões pendentes

Antes da implementação final, decidir:

- Qual percentual padrão inicial do Mercado Livre?
- Vamos começar com cashback em percentual ou em valor estimado?
- A primeira versão mostrará banner automático ou apenas popup?
- O login usará cookie de sessão atual?
- Será necessário token específico para extensão?
- Como será a política de CORS/CSRF?
- Qual será o ID final da extensão publicada?
- A extensão será pública ou não listada inicialmente?
- O admin terá regras de cashback já no MVP ou depois?

## 17. Critérios de aceite do PR 1

Este PR será aceito se:

- A pasta docs/ existir.
- O arquivo docs/extensao_chrome_pr1_documentacao.md existir.
- O conteúdo documentar claramente objetivo, fluxo, arquitetura e próximos PRs.
- Nenhuma funcionalidade do sistema for alterada.
- Nenhum arquivo Python for alterado.
- Nenhum arquivo HTML do sistema for alterado.
- Nenhum arquivo JS do sistema for alterado.
- Nenhum arquivo CSS do sistema for alterado.
- Nenhum arquivo de banco for alterado.
- Apenas documentação Markdown for adicionada ou atualizada.
