# Worker local (PR 2 - modelo híbrido)

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
