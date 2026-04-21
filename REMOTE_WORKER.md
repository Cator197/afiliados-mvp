# Worker local (PR 4 - robustez operacional leve)

## Arquitetura oficial
- **VPS**: API + banco + frontend + controle de jobs/status.
- **Worker local/remoto**: único componente que roda Selenium/Chrome para gerar link.
- A VPS **não** processa Selenium localmente e **não** usa fila em memória no fluxo produtivo.

## Fluxo oficial de processamento
1. Usuário cria job via `POST /api/solicitar-link` (status inicial `na_fila`).
2. Worker busca job via `POST /api/worker/jobs/claim`.
3. Worker finaliza via `POST /api/worker/jobs/<job_id>/success` ou `POST /api/worker/jobs/<job_id>/error`.

## Robustez adicionada no PR 4

### 1) Reclaim simples de jobs presos
- Antes de cada claim, a VPS executa reclaim de jobs em `processando` cujo `claimed_em` excedeu o timeout.
- Esses jobs voltam para `na_fila` (MVP com worker principal único).
- Configuração usada: `JOB_TIMEOUT_SECONDS`.

### 2) Heartbeat mínimo do worker
- O worker envia heartbeat periódico para `POST /api/worker/heartbeat`.
- A VPS registra:
  - `worker_id`
  - `last_heartbeat_em`
  - `last_status`
  - `last_message`
- Configuração usada: `WORKER_HEARTBEAT_INTERVAL_SECONDS`.

### 3) Status operacional para admin/debug
- Endpoint técnico: `GET /api/admin/worker-status` (requer sessão de admin).
- Retorna:
  - último heartbeat do worker
  - status/mensagem do worker
  - indicador simples de inatividade (`inactive`)
  - contagem de jobs `na_fila`, `processando` e `erro`
- Configuração usada: `WORKER_INACTIVE_THRESHOLD_SECONDS`.

## Requisito operacional
- O worker local/remoto é obrigatório para processar jobs.
- Se nenhum worker estiver ativo, os jobs permanecem em `na_fila`.

## Como iniciar
1. Configure as variáveis de ambiente no PC local:
   - `VPS_BASE_URL` (ex.: `https://sua-vps.com`)
   - `WORKER_API_TOKEN`
   - `WORKER_ID` (ex.: `pc-escritorio-01`)
   - `WORKER_POLL_INTERVAL_SECONDS` (ex.: `5`)
   - `WORKER_HEARTBEAT_INTERVAL_SECONDS` (ex.: `15`)
   - `CHROME_PROFILE_DIR` (opcional, recomendado para sessão persistente)
2. Instale dependências (`pip install -r requirements.txt`).
3. Inicie o worker local:
   - `python remote_worker.py`

## Login manual no Mercado Livre
- O worker sobe/reutiliza um único navegador Chrome (headful) com perfil persistente.
- Se não estiver logado, entra em modo **aguardando login manual** e pausa o polling.
- Faça login manualmente no mesmo navegador aberto pelo Selenium.

## Manutenção de sessão / relogin
- Se a sessão cair durante um job, o worker não fecha o navegador.
- O estado muda para aguardando login manual no mesmo browser.
- Após relogar manualmente, o worker detecta sessão restabelecida e volta a processar jobs.
