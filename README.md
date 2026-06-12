# Melo Reparos — Protótipo Etapa 4

Esta entrega adiciona o módulo de **Produção** e aprofunda o módulo de **Complementos** usando HTML, CSS e JavaScript puro. Os dados são fictícios, centralizados em `assets/js/mock-data.js`, e as alterações da sessão usam `sessionStorage` para simular backend sem persistência definitiva.

## Como abrir e testar

Abra os arquivos diretamente no navegador ou sirva a pasta do projeto com um servidor estático:

```bash
python3 -m http.server 8765
```

Depois acesse:

- Produção: `http://127.0.0.1:8765/paginas/producao.html`
- Complementos: `http://127.0.0.1:8765/paginas/complementos.html`
- Detalhe de complemento: `http://127.0.0.1:8765/paginas/complemento-detalhes.html?id=comp-001`
- Detalhe da OS principal: `http://127.0.0.1:8765/paginas/os-detalhes.html?id=os-1042`

## Arquivos criados

- `paginas/producao.html`
- `paginas/complementos.html`
- `paginas/complemento-detalhes.html`
- `paginas/os-detalhes.html`
- `assets/css/melo.css`
- `assets/js/mock-data.js`
- `assets/js/app-shared.js`
- `assets/js/producao.js`
- `assets/js/complementos.js`
- `assets/js/complemento-detalhes.js`
- `assets/js/os-detalhes.js`
- `README.md`

## Arquivos modificados

Nesta base não havia os arquivos estáticos das etapas anteriores da Melo Reparos. A implementação foi aplicada diretamente no projeto atual, sem duplicar o projeto, sem criar pasta de versão e sem remover arquivos existentes.

## Interações simuladas

### Produção

- Alternância entre Kanban, tabela e agenda com preferência salva em `localStorage`.
- Indicadores superiores clicáveis, aplicando filtros operacionais.
- Filtros por pesquisa, placa, OS, cliente, veículo, etapa, condição, atraso, entrega, prioridade e datas.
- Kanban por etapa principal: Desmontagem, Funilaria, Preparação, Pintura, Montagem e Polimento.
- Áreas separadas para aguardando agendamento, agendados e finalizados aguardando entrega.
- Condições paralelas exibidas nos cards sem substituir a etapa principal.
- Movimentação por botão e por arrastar/soltar, sempre com modal de confirmação antes de alterar a OS.
- Retorno de etapa detectado quando a nova etapa é anterior à atual; o motivo passa a ser obrigatório.
- Finalização alerta sobre pendências simuladas antes de confirmar.
- Histórico de movimentação atualizado na sessão.
- Gerenciamento visual de condições paralelas: adicionar, encerrar e reabrir.
- Bloco destacado para veículos há muito tempo na etapa.
- Capacidade por etapa com dados fictícios e configuráveis.

### Complementos

- Lista em tabela e cards.
- Indicadores clicáveis por status e valor aguardando aprovação.
- Filtros por complemento, OS, placa, cliente, seguradora, status, período, dias aguardando, impacto e valores.
- Detalhe por URL com `id`, incluindo estado de não encontrado.
- Ações simuladas para enviar, aprovar, aprovar parcialmente, recusar, cancelar, concluir, anexar documento e adicionar observação.
- Aprovação altera valor da OS, previsão de entrega, itens aprovados, condição paralela e histórico.
- Recusa encerra a condição paralela relacionada e registra histórico.
- Novo complemento cria registro temporário, vincula à OS e adiciona condição paralela `Complemento pendente`.

## Dados fictícios

`assets/js/mock-data.js` contém 14 OSs, incluindo 12+ ativas distribuídas pelas etapas, OS 1042 como demonstração principal, veículo aguardando peça, complemento pendente, veículo atrasado, entrega hoje, retorno de Preparação para Funilaria, duas condições paralelas, finalizado aguardando entrega, agendado para entrar, serviço terceirizado e complemento aprovado que alterou previsão.

Também contém 8 complementos com os status solicitados: rascunho, solicitado, aguardando aprovação, aprovado, aprovado parcialmente, recusado e concluído.

## Limitações

- Não há backend, autenticação real, banco de dados ou persistência definitiva.
- Permissão de movimentação é simulada pelo usuário fictício selecionado no topo da Produção.
- Capacidade por etapa é apenas visual e configurável.
- Compras, financeiro, relatórios finais, integrações externas e NF não foram implementados.
- Anexos e exportações são simulações visuais.
- Drag and drop foi incluído com confirmação modal; caso algum navegador antigo apresente limitação, o botão **Movimentar** oferece o fluxo estável equivalente.

## Decisões assumidas

- Como não havia backend, `sessionStorage` mantém alterações somente durante a sessão e `localStorage` guarda preferências de visualização/usuário.
- Complemento e aguardando peça foram modelados como condições paralelas, nunca como etapa principal.
- OS cancelada não aparece como ativa na produção; finalizado aguardando entrega aparece em área separada.
- A produção é controlada por setor/etapa, não por funcionário individual.
- Datas usam o dia fictício da etapa: 12/06/2026.

## Correções e compatibilidade com etapas anteriores

- Foi criada uma página de detalhe de OS para demonstrar a aba Produção sincronizada com as mesmas funções compartilhadas da página Produção.
- A OS 1042 permanece como registro principal de demonstração.
- As páginas anteriores existentes no repositório não foram alteradas.

## Sugestão de mensagem de commit

```text
feat: implementa produção e complementos no protótipo
```
