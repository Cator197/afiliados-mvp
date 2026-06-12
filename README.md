# Melo Reparos — Protótipo Etapa 5

Esta entrega implementa o módulo completo de **Compras, Itens e Recebimentos** do protótipo da Melo Reparos, mantendo HTML, CSS e JavaScript puro. Os dados seguem centralizados em `assets/js/mock-data.js`, e as alterações feitas na sessão são simuladas em `sessionStorage`; preferências de visualização continuam em `localStorage`.

## Como abrir e testar

Abra os arquivos diretamente no navegador ou sirva a pasta do projeto com um servidor estático:

```bash
python3 -m http.server 8765
```

Depois acesse:

- Início: `http://127.0.0.1:8765/paginas/inicio.html`
- Compras: `http://127.0.0.1:8765/paginas/compras.html`
- Detalhe de compra: `http://127.0.0.1:8765/paginas/compra-detalhes.html?id=compra-001`
- Itens pendentes: `http://127.0.0.1:8765/paginas/itens-pendentes.html`
- Produção: `http://127.0.0.1:8765/paginas/producao.html`
- Complementos: `http://127.0.0.1:8765/paginas/complementos.html`
- Detalhe de complemento: `http://127.0.0.1:8765/paginas/complemento-detalhes.html?id=comp-001`
- Detalhe da OS principal: `http://127.0.0.1:8765/paginas/os-detalhes.html?id=os-1042`

## Arquivos criados nesta etapa

- `paginas/inicio.html`
- `paginas/compras.html`
- `paginas/compra-detalhes.html`
- `paginas/itens-pendentes.html`
- `assets/js/inicio.js`
- `assets/js/compras.js`
- `assets/js/compra-detalhes.js`
- `assets/js/itens-pendentes.js`

## Arquivos modificados nesta etapa

- `assets/js/mock-data.js`
- `assets/js/app-shared.js`
- `assets/js/os-detalhes.js`
- `assets/js/producao.js`
- `paginas/producao.html`
- `paginas/complementos.html`
- `paginas/complemento-detalhes.html`
- `paginas/os-detalhes.html`
- `README.md`

## Interações simuladas

### Compras

- Cabeçalho com breadcrumb, ações principais, última atualização fictícia e total de compras encontradas.
- Indicadores clicáveis para compras em aberto, itens aguardando compra, pedidos aguardando entrega, recebimentos parciais, atrasos, veículos aguardando peça, compras sem conta a pagar e valor pendente.
- Três visualizações: **Pedidos**, **Itens** e **Fornecedores**, com preferência salva localmente.
- Filtros por pesquisa livre, pedido, item, código, fornecedor, OS, placa/veículo, status do pedido, status do item, status financeiro, períodos, previsão, atrasados, parcial, sem conta e responsável.
- Ações rápidas por pedido e item: abrir detalhe, registrar recebimento, gerar conta a pagar, marcar sem lançamento, anexar documento, registrar devolução, cancelar compra e alterar rateio.
- Estados bloqueados com botões desabilitados quando a ação não é permitida pelo status.

### Nova compra e rateio

- Modal de nova compra com dados gerais, múltiplos itens e vínculo por item com uma ou duas OSs.
- Resumo calculado com quantidade de itens, total, valor rateado, diferença e quantidade de OSs atendidas.
- Rateio por valor, percentual e quantidade com validação visual de limites.
- Valor não rateado é permitido apenas mediante confirmação simulada.
- Ao confirmar, a compra temporária é criada, itens são vinculados às OSs e alertas/condições de peças pendentes são atualizados durante a sessão.

### Recebimentos, divergências e devoluções

- Recebimento total e parcial por pedido, mantendo itens pendentes quando a quantidade recebida é menor que a pedida.
- Status operacional do pedido é recalculado visualmente com base nos itens.
- Registro de avarias, item incorreto, divergência de quantidade e quantidade maior que o pedido.
- Devolução parcial/total simulada, sem apagar o recebimento original e mantendo histórico.
- Recebimentos atualizam a OS vinculada durante a sessão e sugerem encerramento da condição “Aguardando peça” quando todos os itens são recebidos, sem encerramento automático.

### Conta a pagar

- Compras não geram conta a pagar automaticamente.
- Alerta: “Esta compra ainda não possui uma conta a pagar.” quando a compra exige lançamento e não possui conta vinculada.
- Fluxo de geração com revisão de dados antes da confirmação.
- Opção “Não necessita lançamento financeiro” com motivo, responsável, data e observação.
- Aba Financeiro mostra integração visual com conta a pagar fictícia, diferenças entre valor da compra, valor lançado e valor rateado.

### Detalhe da compra

- Página `compra-detalhes.html?id=...` com estado de não encontrado.
- Cabeçalho com pedido, fornecedor, status, valor, previsão, atraso, recebimento, financeiro, quantidade de OSs e responsável.
- Abas: Visão geral, Itens, Ordens de Serviço, Recebimentos, Financeiro, Documentos e Histórico.
- Itens expansíveis com rateio, recebimentos, devoluções, observações e documentos relacionados.
- Histórico em linha do tempo com criação, recebimento, devolução, documento, conta a pagar e cancelamento.

### Integrações

- **OS 1042** permanece como registro principal de demonstração, agora com itens de compra, item parcialmente recebido, condição “Aguardando peça”, fornecedor, previsão e custo rateado.
- Aba Compras da OS mostra pedidos vinculados, itens, fornecedor, quantidade destinada, recebida, pendência, previsão, custo estimado, custo real, rateio, conta a pagar, divergências e devoluções.
- Produção mostra quantidade de peças pendentes e link “Ver peças”, preservando a etapa principal da OS.
- Página Inicial exibe alertas de compra atrasada, peça prevista para hoje, compra sem conta a pagar, recebimento parcial, divergência aberta e veículo bloqueado por peça.

## Dados fictícios

`assets/js/mock-data.js` contém 11 compras e 25 itens, cobrindo:

1. pedido realizado aguardando entrega;
2. pedido parcialmente recebido;
3. pedido recebido integralmente;
4. pedido atrasado;
5. compra sem conta a pagar;
6. compra marcada como sem necessidade de lançamento;
7. compra com vários itens;
8. compra atendendo várias OSs;
9. compra com devolução parcial;
10. compra cancelada;
11. rascunho com item sem rateio completo.

Também há item destinado a uma única OS, item rateado entre duas OSs, item parcialmente recebido, item atrasado, item devolvido, item com divergência, item sem fornecedor, item sem rateio completo, item ligado à OS 1042 e item de complemento aprovado.

## Limitações

- Não há backend, banco de dados, autenticação real ou persistência definitiva.
- Financeiro é apenas integração visual com contas a pagar fictícias; não há módulo financeiro completo, conciliação, bancos ou parcelas reais.
- Não há cotação com múltiplos fornecedores, estoque completo, contabilidade, emissão fiscal, importação real ou integrações externas.
- Anexos, exportações, downloads e impressão são simulações visuais.
- As validações são de protótipo e acontecem no navegador durante a sessão.

## Decisões assumidas

- “Aguardando peça” foi mantido como condição paralela e nunca substitui a etapa produtiva principal.
- Compras canceladas ficam no histórico, mas não entram como valor real ativo.
- Devoluções reduzem a quantidade válida recebida e permanecem registradas.
- A conta a pagar só é criada após ação explícita do usuário.
- Dados de fornecedor, OS e custos foram mantidos consistentes para demonstrar o fluxo completo sem backend.
- Datas usam o dia fictício do protótipo: 12/06/2026.

## Correções e compatibilidade com etapas anteriores

- Navegação das páginas estáticas foi atualizada para incluir Início, Compras e Itens pendentes.
- A página de OS foi ampliada com a aba visual de Compras sem remover produção ou complementos.
- Produção ganhou sinalização de peças pendentes sem alterar a etapa principal da OS.
- Complementos e Produção continuam disponíveis e usando os mesmos dados compartilhados.

## Sugestão de mensagem de commit

```text
feat: implementa módulo de compras e recebimentos
```

## Etapa 6 — Financeiro, Fluxo de Caixa e Rentabilidade

A Etapa 6 adiciona o módulo financeiro simulado da Melo Reparos, preservando o protótipo local em HTML, CSS e JavaScript puro, sem backend e sem banco de dados definitivo.

### Arquivos criados

- `paginas/financeiro.html` — visão geral financeira com indicadores, período, alertas, próximos vencimentos e histórico.
- `paginas/contas-receber.html` — contas a receber em modos de contas, parcelas e pagadores.
- `paginas/contas-pagar.html` — contas a pagar em modos de contas, parcelas, fornecedores e categorias.
- `paginas/fluxo-caixa.html` — fluxo de caixa mensal com entradas/saídas previstas e realizadas.
- `paginas/rentabilidade.html` — rentabilidade por OS, lucro estimado, lucro realizado e fechamento financeiro.
- `paginas/regras-pagamento.html` — regras de pagamento e taxas de cartão fictícias.
- `paginas/categorias-financeiras.html` — categorias financeiras iniciais.
- `assets/js/financeiro-core.js` — dados, cálculos e operações financeiras centralizadas.
- `assets/js/financeiro-ui.js` — modais e helpers visuais compartilhados do financeiro.
- `assets/js/financeiro.js`, `assets/js/contas-receber.js`, `assets/js/contas-pagar.js`, `assets/js/fluxo-caixa.js`, `assets/js/rentabilidade.js`, `assets/js/regras-pagamento.js`, `assets/js/categorias-financeiras.js` — scripts específicos de cada página.

### Arquivos modificados

- `assets/js/app-shared.js` — sessão local atualizada para a versão 6.
- `assets/js/inicio.js` — painel inicial com recebimentos, pagamentos, contas vencidas, saldo previsto, OS com saldo e alertas financeiros.
- `assets/js/producao.js` — agenda semanal enriquecida com eventos financeiros simulados.
- `assets/js/os-detalhes.js` — aba financeira da OS com receitas, custos, margem, pendências, fechamento e reabertura.
- `assets/css/melo.css` — estilos responsivos para indicadores financeiros, linha do tempo, modais e fluxo de caixa.
- Páginas HTML existentes — navegação principal ampliada com Financeiro, Receber, Pagar, Fluxo e Rentabilidade.

### Interações simuladas

- Criar conta a receber, gerar parcelas, recalcular taxa de cartão e revisar a fórmula antes de confirmar.
- Criar conta a pagar somente após confirmação explícita, inclusive vinculada a compra ou OS.
- Registrar recebimento total, recebimento parcial, pagamento total, pagamento parcial, descontos, juros e estornos.
- Filtrar contas por texto, status, pagador, fornecedor, categoria, vencidas, parciais e valores.
- Alternar fluxo de caixa entre previsto/realizado e entradas/saídas, navegar por mês e consultar pendências.
- Consultar lucro estimado, lucro realizado provisório, margem por OS, OS com prejuízo e OS sem fechamento.
- Fechar financeiramente uma OS, bloquear fechamento silencioso quando houver pendências e permitir fechamento com ressalva mediante justificativa.
- Reabrir fechamento financeiro com motivo e registro em histórico.

### Dados fictícios e decisões assumidas

- Os dados da Etapa 6 são centralizados e sincronizados em `assets/js/financeiro-core.js`, usando `sessionStorage` por meio dos helpers existentes.
- Foram cadastradas mais de 18 contas a receber, 18 contas a pagar, mais de 30 parcelas, 12 baixas, 6 regras de pagamento, 6 taxas de cartão e 19 categorias financeiras.
- A OS 1042 permanece como principal demonstração: seguradora, franquia do cliente, serviço adicional, taxa de cartão, compra vinculada, conta a pagar, recebimento parcial, lucro estimado e lucro realizado provisório com pendências.
- O saldo inicial é apenas fictício para visualização do fluxo de caixa e não representa conta bancária real.
- O lucro realizado é exibido como provisório quando há receitas pendentes, contas vencidas, compras sem conta, complementos pendentes ou custos não liquidados.
- Não foram implementados boleto, nota fiscal, conciliação bancária, integração externa, backend, banco de dados ou múltiplas contas bancárias.

### Como abrir e testar

1. Abra `paginas/inicio.html` diretamente no navegador.
2. Navegue para `Financeiro`, `Receber`, `Pagar`, `Fluxo`, `Rentabilidade`, `Regras` e `Categorias` pelos menus.
3. Para reiniciar os dados da sessão, limpe o `sessionStorage` do navegador ou altere a versão da chave local em `assets/js/app-shared.js`.
4. Teste responsividade em 1440 px, 1024 px, 768 px e 390 px usando as ferramentas de desenvolvedor.

### Correções e integrações de etapas anteriores

- Compras da Etapa 5 passam a atualizar status financeiro quando há conta a pagar vinculada.
- Compras sem conta a pagar continuam como alerta até confirmação ou justificativa.
- A Página Inicial passa a refletir os mesmos valores financeiros usados nas listas.
- A Agenda da Produção passa a exibir vencimentos, previsões de recebimento/pagamento, parcelas e fechamento financeiro.
- A aba da OS agora cruza receitas, custos, compras, complementos e histórico financeiro.

### Limitações do protótipo

- Todas as operações são simuladas no navegador e não persistem fora da sessão local.
- As regras fiscais, tributárias, bancárias e contábeis são apenas placeholders visuais.
- O custo interno por hora de funcionário ainda não é calculado; a estrutura ficou preparada para etapa futura.

Sugestão de commit: `feat: implementa financeiro, fluxo de caixa e rentabilidade`
