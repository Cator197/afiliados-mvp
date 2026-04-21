# Worker local (PR 3 - modelo híbrido desacoplado)

## Arquitetura oficial após PR 3
- **VPS**: API + banco + frontend + controle de status/jobs.
- **Worker local/remoto**: único componente que roda Selenium/Chrome para gerar link.
- A VPS **não** processa Selenium localmente e **não** usa fila em memória (`queue.Queue`) no fluxo produtivo.
- Fluxo oficial de processamento:
  1. Usuário cria job via `POST /api/solicitar-link` (status inicial `na_fila`).
  2. Worker busca job via `POST /api/worker/jobs/claim`.
  3. Worker finaliza via `POST /api/worker/jobs/<job_id>/success` ou `POST /api/worker/jobs/<job_id>/error`.

## Requisito operacional
- O worker local/remoto é obrigatório para processar jobs.
- Se nenhum worker estiver ativo, os jobs permanecem em `na_fila` até alguém claimar.

## Como iniciar
1. Configure as variáveis de ambiente no PC local:
   - `VPS_BASE_URL` (ex.: `https://sua-vps.com`)
   - `WORKER_API_TOKEN`
   - `WORKER_ID` (ex.: `pc-escritorio-01`)
   - `WORKER_POLL_INTERVAL_SECONDS` (ex.: `5`)
   - `CHROME_PROFILE_DIR` (opcional, mas recomendado para perfil persistente)
2. Instale dependências (`pip install -r requirements.txt`).
3. Inicie o worker local:
   - `python remote_worker.py`

## Login manual no Mercado Livre
- O worker sobe/reutiliza um único navegador Chrome (headful) com perfil persistente.
- Se não estiver logado, o worker entra em modo **aguardando login manual** e pausa o polling.
- Faça login manualmente no mesmo navegador aberto pelo Selenium.

## Manutenção de sessão / relogin
- Se a sessão cair durante um job, o worker **não fecha** o navegador.
- O estado muda para aguardando login manual no mesmo browser.
- Após relogar manualmente, o worker detecta sessão restabelecida e volta a processar jobs.
