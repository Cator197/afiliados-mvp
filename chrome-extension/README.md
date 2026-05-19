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
7. Verificar se o banner aparece.
8. Clicar no ícone da extensão e verificar o popup.

## O que este PR faz

- Cria estrutura inicial da extensão.
- Cria manifest.json.
- Cria popup básico.
- Captura URL atual no popup.
- Detecta se a aba atual é Mercado Livre.
- Insere banner visual no Mercado Livre.
- Não integra com backend.
- Não gera link ainda.

## O que fica para próximos PRs

- Detectar página de produto.
- Criar endpoints no backend.
- Verificar login.
- Gerar job.
- Consultar status.
- Mostrar link final.
- Calcular cashback estimado.
