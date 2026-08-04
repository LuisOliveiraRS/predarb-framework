# CLAUDE.md — Contexto Mestre do PredArb Framework

> Coloque este arquivo na raiz de `C:\predarb-framework` para servir como contexto principal do Claude Code no VSCode.
>
> Data do contexto: 03/08/2026.
>
> Estado: as Fases 17 a 20C estão implantadas em produção. As Fases 18 a 20C chegaram lá em **03/08/2026**, no push que sincronizou `main` com `origin/main`; até então estavam apenas locais. O coletor cripto tem job de scheduler e API, **ambos desligados por default e desligados em produção**. A Fase 20D — o painel do scanner no dashboard — está implementada e commitada na branch `feature/phase-20d-crypto-dashboard`, sem merge e sem deploy.
>
> A pendência de segurança da seção 4 foi **fechada em 02/08/2026**: a autenticação passou a ser exigida em produção. Ver seção 4 para o estado atual e para os defeitos conhecidos da experiência de login.

---

## 1. Regras obrigatórias para o Claude Code

Antes de alterar qualquer arquivo:

1. Leia este documento inteiro.
2. Execute `git status --short --branch` e revise o diff atual.
3. Preserve integralmente as alterações não commitadas da Fase 17.
4. Não execute `git commit`, `push`, `merge`, `tag`, `deploy`, `stash`, `reset` ou descarte sem autorização explícita do usuário.
5. Não sobrescreva arquivos completos sem comparar a versão atual.
6. Faça uma alteração útil por vez e rode testes focados.
7. Rode a suíte completa somente em marcos relevantes, evitando repetições.
8. Nunca solicite, imprima ou registre senhas, API secrets, private keys, seed phrases, códigos TOTP, JWTs, service-role keys ou URLs de banco com senha.
9. Não habilite execução financeira automaticamente.
10. Todo erro, timeout, dado stale, divergência ou incerteza deve impedir execução: o sistema é fail-closed.
11. O ambiente principal é Windows PowerShell.
12. Use o Python da virtualenv explicitamente:

```powershell
C:\predarb-framework\backend\.venv\Scripts\python.exe
```

---

## 2. Resumo executivo

O PredArb Framework é uma plataforma FastAPI modular para detectar, acompanhar e futuramente executar estratégias de arbitragem.

A base atual já possui:

- arquitetura de conectores;
- event bus;
- scheduler APScheduler;
- persistência SQLAlchemy/Supabase;
- simulador Paper;
- Shadow Runtime;
- APIs REST;
- dashboard web autenticado;
- autenticação Supabase com MFA/TOTP;
- dados reais públicos de Polymarket e Kalshi;
- radar de oportunidades;
- tendências e histórico;
- cache, single-flight e persistência de observações;
- coletor automático em segundo plano implementado localmente na Fase 17;
- proteções contra execução financeira acidental.

A nova missão é acrescentar um domínio separado de arbitragem de criptoativos entre CEX, DEX e Web3. A evolução deve seguir esta ordem:

```text
dados públicos
-> normalização
-> livros em tempo real
-> cálculo líquido
-> Paper
-> replay/backtest
-> contas privadas read-only
-> testnet
-> canary real explicitamente autorizado
-> expansão gradual
```

O sistema não deve prometer lucro. Diferenças aparentes podem desaparecer por taxas, slippage, profundidade insuficiente, latência, gas, MEV, fills parciais, falhas de API, risco de contraparte e movimentos de mercado.

---

## 3. Repositório e estado atual

### Caminhos

```text
Raiz:     C:\predarb-framework
Backend:  C:\predarb-framework\backend
Venv:     C:\predarb-framework\backend\.venv
Python:   C:\predarb-framework\backend\.venv\Scripts\python.exe
```

### Branch atual

```text
feature/phase-20d-crypto-dashboard
```

As branches anteriores já foram merjadas na `main`. Confira sempre com `git status --short --branch` antes de confiar neste campo: ele já ficou defasado três vezes.

**`main` e `origin/main` estão sincronizados desde 03/08/2026.** Antes disso `main` acumulava dois commits locais da Fase 20C, e o repositório remoto ficava atrás do que a seção 5 descrevia como pronto.

### Base conhecida

```text
574d383
```

Esse commit corresponde ao merge da correção de isolamento do banco de observações da Fase 16.

### Commits da Fase 17

A Fase 17 foi merjada na `main` pelo PR #16 e tagueada.

```text
823d84f Merge pull request #16
        tag phase-17-background-radar-collector

0b649a3 chore: version the env template and document phase 16/17 settings
f65d2ba docs: sync CLAUDE.md with real phase 17 state
a556744 feat: throttle external radar force refresh and require auth
78d0fef feat: collect real opportunity radar in background
```

Total do PR: 16 arquivos, +3945/−94.

O arquivo `CLAUDE_CODE_PROMPT_INICIAL.txt` permanece fora do versionamento: duplica a seção 30 deste documento e tende a divergir dela.

### Última validação completa

```text
996 passed, 10 deselected, 2 warnings in 148.23s
git diff --check: aprovado
node --check dashboard.js: sintaxe aprovada
auditoria de flags financeiras: nenhuma ocorrência True em app/
varredura de segredos no diff: nenhum indício
```

Evolução: 688 antes da Fase 18, 752 depois dela, 799 com a 19A, 840 com a 19B, 880 com a 19C1, 912 com a 19C2, 939 com a 20A, 965 com a 20B, 981 com a 20C, 996 com a 20D. Mais 10 de integracao, fora da suite padrao.

Se a suíte completa abortar com `MemoryError` durante a coleta, o problema é a máquina, não o código. Rodar em lotes contorna:

```powershell
# 107 arquivos divididos em 4 lotes evitam importar tudo de uma vez
Get-ChildItem tests\test_*.py | Sort-Object Name
```

O total esperado permanece 981, com 10 deselected.

### Teste instável conhecido

```text
tests/test_paper_certification_assurance_gate_history_runtime.py
    ::test_runtime_processes_periodic_cycles
```

Falha intermitentemente na suíte completa e passa isolado. A causa está no próprio teste, não no código: ele inicia um runtime com `interval_seconds=0.02`, dorme `0.08` e exige ao menos dois ciclos. Sob carga da suíte inteira, o event loop nem sempre entrega quatro janelas de 20 ms.

Observado em 02/08/2026 durante a Fase 19C1, com nova execução passando em seguida. **Não é regressão** — nenhum arquivo de `paper/` foi tocado pelas fases 18 e 19. Se falhar, reexecute antes de investigar. A correção adequada seria substituir o tempo de parede por relógio controlado, como fizeram `rate_limiter.py` e `backoff.py`.

Warnings conhecidos:

1. StarletteDeprecationWarning no TestClient/httpx.
2. InsecureKeyLengthWarning em teste negativo de JWT da Fase 13B.

Não são regressões da Fase 17.

Ao atualizar este documento, confira o estado real com `git status --short --branch`, `git log --oneline` e a contagem de testes antes de reescrever esta seção. Ela já ficou defasada uma vez.

---

## 4. Produção atual

### Backend e dashboard

```text
https://predarb-framework.onrender.com
https://predarb-framework.onrender.com/dashboard
```

Hospedagem: Render Free.

#### Auto-deploy: `push` em `main` é deploy

O serviço está com **Auto-Deploy ligado, on commit, no branch `main`**. Confirmado em 03/08/2026.

Consequência que não se enxerga pelo repositório: **não existe `render.yaml` versionado**, a configuração vive só no painel do Render, e portanto nada no código revela esse acoplamento. `git push origin main` **é** um deploy de produção. A regra 4 da seção 1 trata `push` e `deploy` como autorizações separadas — com essa configuração, autorizar um autoriza o outro, e isso precisa ser dito na hora de pedir autorização.

Para salvar commits sem deployar, empurre para uma branch de feature.

#### Deploy das Fases 18 a 20C — 03/08/2026

O push que sincronizou `main` levou todo o domínio cripto a produção. Validação logo após:

```text
GET /health                  200  {"status":"healthy","version":"0.1.0"}
GET /auth/config             200  enabled=true  dashboard_required=true
GET /crypto/scanner/status   404 antes -> 401 depois
GET /rota-inexistente        404  (controle)
coletor da Fase 17           29 cycles / 29 successes / 0 failures / READY
flags financeiras            todas false
```

O par **`404` na rota inexistente e `401` no endpoint cripto** é a evidência que importa: prova que a rota existe **e** que a autenticação do roteador não virou no-op — exatamente a falha da Fase 14/17 que a 20C se propôs a evitar. Um `401` isolado não provaria nada sem o controle ao lado.

O coletor da Fase 17 atravessou o deploy sem falha. O scanner cripto permanece desligado: `CRYPTO_SCANNER_ENABLED` não está definido no ambiente, e o default é `false`.

Armadilha de diagnóstico: contadores como `cycles` são de memória e zeram no restart, então servem para estimar o uptime do processo — mas o `WebFetch` **cacheia por URL durante 15 minutos**, e reconsultar a mesma URL devolve a resposta antiga. Varie a query string ao comparar antes e depois de um deploy.

Consequências:

- o processo pode dormir ou reiniciar;
- memória e cache são locais ao processo;
- persistência Supabase deve sobreviver aos reinícios;
- não assumir coordenação distribuída entre múltiplos workers.

Um reinício zera a memória: `history_points` volta a `0` e o snapshot volta a `WARMING_UP` até o primeiro ciclo do coletor. Isso é esperado. O histórico persistente é reidratado do banco dedicado.

### Autenticação em produção — ATIVA desde 02/08/2026

A autenticação da Fase 13B passou a ser **exigida** no ambiente do Render. Estado verificado em 02/08/2026:

```text
GET /auth/config          -> enabled=true  dashboard_required=true

exigem credencial (401 sem sessao valida):
    /dashboard/api/*                     inclui /status e /health do dashboard
    /router/*
    /real-markets/radar/opportunities
    /auth/me

publicos por projeto (200):
    /dashboard   /login   /health
    /real-markets/radar/snapshot
    /real-markets/radar/collector/status
    /docs   /openapi.json
```

Variáveis que ativam o comportamento, ambas necessárias:

```text
AUTH_ENABLED=true
AUTH_REQUIRED_FOR_DASHBOARD=true
```

Rollback de qualquer etapa: `AUTH_REQUIRED_FOR_DASHBOARD=false` reabre o acesso preservando o resto; `AUTH_ENABLED=false` desliga o subsistema inteiro. Nenhum dos dois afeta o coletor da Fase 17, confirmado em produção.

#### Como verificar — e como NÃO verificar

Use `GET /auth/config`. Ele é público, não expõe segredo nenhum e devolve `enabled` e `dashboard_required` lidos direto do `settings`. Foi a ferramenta que resolveu o diagnóstico de 02/08/2026 e deve ser o primeiro comando de qualquer investigação de autenticação.

**Não use `GET /dashboard` como evidência.** A rota HTML em `dashboard/router.py:39` não tem dependência de autenticação por projeto — serve apenas o shell, e os dados vêm de `/dashboard/api/*`, esses sim protegidos. `/dashboard` responde 200 com ou sem autenticação exigida. A versão anterior desta seção tratava esse 200 como sintoma do problema, o que é incorreto e induz a concluir erradamente que a ativação falhou.

O teste válido de fechamento é `/dashboard/api/status` responder 401 sem credencial.

#### Pré-requisitos de boot

Validados em `settings.py:272-329`. Qualquer um faltando impede a aplicação de subir:

- `SUPABASE_URL` preenchida e começando com `https://` fora de DEBUG;
- `SUPABASE_PUBLISHABLE_KEY` preenchida (é a chave pública; a service-role nunca entra aqui);
- `SUPABASE_JWT_AUDIENCE` não vazia, default `authenticated`;
- `AUTH_COOKIE_SECURE=true` fora de DEBUG;
- `SUPABASE_JWKS_CACHE_TTL_SECONDS` entre 60 e 600.

Detalhe que custou tempo: esse bloco inteiro está dentro de `if self.AUTH_ENABLED:`. Com a flag falsa, `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` **nunca são checadas**. Um boot bem-sucedido com `AUTH_ENABLED=false` não diz absolutamente nada sobre a validade dessas variáveis.

Um boot recusado por erro de validação **não derruba produção**: o Render mantém o deploy anterior servindo. Confirmado em 02/08/2026.

#### Armadilha do prefixo NEXT_PUBLIC_

O painel do Supabase exibe os snippets de configuração no formato do Next.js, com prefixo `NEXT_PUBLIC_`. Este backend é FastAPI e **não** usa prefixo: `settings.py:138-143` declara `SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)`.

Consequências:

- `case_sensitive=False` — maiúsculas/minúsculas não importam;
- não há `env_prefix` — o nome é literal;
- **`extra="ignore"` descarta em silêncio** qualquer variável cujo nome não corresponda a um campo declarado.

Variáveis nomeadas `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` aparecem corretamente configuradas no painel do Render e chegam vazias ao processo, sem aviso algum. Os nomes corretos são `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY`. O mesmo vale para qualquer espaço invisível no nome da chave.

Sintoma correspondente no boot:

```text
ValidationError: AUTH_ENABLED exige SUPABASE_URL.
```

#### Sobre o MFA

`require_dashboard_user` chama `user.require_mfa()`, e `has_mfa` é `aal == "aal2"` (`auth/models.py:45`) — propriedade **da sessão**, não do cadastro. Ter o fator TOTP inscrito não basta: o login precisa efetivamente elevar a sessão a `aal2`.

Não há risco de deadlock de inscrição. `mfa_router.py:18` usa `require_authenticated_user`, que apenas autentica e **não** exige MFA (`dependencies.py:139-148`). Uma sessão em `aal1` consegue acessar `/auth/mfa/*` para inscrever e verificar o fator, e `mfa_router.py:35` reemite os cookies já elevados.

O frontend também cobre o caso: `session.js:196` detecta sessão sem MFA e redireciona para `/mfa` em vez de morrer num 403.

### Defeitos conhecidos da experiência de autenticação

Levantados em 02/08/2026 durante a ativação. Ambos são de código, não de configuração, e **não estão corrigidos**.

#### 1. A Etapa 1 do rollout em duas etapas é inexecutável

`auth.js:79-88`:

```javascript
async function checkExistingSession(config) {
    if (
        !config.enabled ||
        !config.dashboard_required
    ) {
        window.location.replace(
            config.after_login_path || "/dashboard"
        );
        return true;
    }
```

Com `enabled=true` e `dashboard_required=false` — exatamente o estado intermediário que a ativação em duas etapas propunha — a página de login expulsa o usuário para o dashboard antes de renderizar o formulário. É o único estado em que **não se consegue fazer login pela interface**.

Isso invalida o propósito da Etapa 1, que era validar credenciais e MFA antes de fechar o acesso. Na prática o rollout precisa ir direto ao estado final, porque é `dashboard_required=true` que destrava o formulário. O risco disso é baixo e reversível: o rollback é uma variável de ambiente.

Correção sugerida: só redirecionar quando `!config.enabled`, ou quando já existir sessão válida.

#### 2. Uma única mensagem para causas distintas

`session_client.py:62-65` colapsa **400, 401 e 403** do Supabase em `InvalidCredentialsError`:

```python
if response.status_code in {400, 401, 403}:
    raise InvalidCredentialsError("E-mail ou senha invalidos.")
```

E `router.py:144-160` mapeia `InvalidCredentialsError`, `InvalidAccessTokenError` e `SessionRefreshError` todos para `Credenciais ou sessao invalidas.`

Ou seja, a mesma frase na tela pode significar:

- senha ou e-mail errados;
- chave de API rejeitada pelo Supabase;
- e-mail não confirmado;
- token válido na emissão mas reprovado na verificação (issuer, audience, algoritmo, JWKS).

O login tem duas etapas internas (`router.py:190-200`): `password_login` e, em seguida, `authenticate(access_token)`. As duas falham com texto idêntico, o que torna impossível distinguir "senha errada" de "token rejeitado" pela interface.

Correção sugerida: manter a mensagem genérica para o usuário final, mas registrar a causa real em log estruturado, sem vazar credencial.

Técnica de diagnóstico que funcionou, para reuso futuro: comparar `auth.users.last_sign_in_at` antes e depois da tentativa de login. Esse campo só avança quando a **primeira** etapa tem sucesso, o que divide o problema exatamente ao meio. Atenção, porém: login por magic link ou por link de recuperação também atualiza o campo, então a comparação precisa ser antes/depois da tentativa específica que se quer investigar.

#### Limite de e-mail do Supabase

O serviço de e-mail embutido tem limite de taxa baixo no plano gratuito. Recuperação de senha e magic link param de funcionar com `limite de taxa de e-mail ultrapassado`. Alternativas: aguardar a janela reiniciar, configurar SMTP próprio, ou definir a senha direto no SQL Editor com `crypt(...)`/`gen_salt('bf')`.

### Supabase

```text
Projeto: predarb-production
Project ref: ikzqwpyyggluueculhuh
URL pública: https://ikzqwpyyggluueculhuh.supabase.co
```

Nunca versionar senha, Session Pooler URI completa, service-role key, JWT secret, chave de carteira ou credencial de corretora.

### Observações persistentes

Tabela:

```text
public.real_market_observations
```

Características:

- RLS habilitado;
- sem políticas públicas;
- `anon` e `authenticated` sem leitura/escrita;
- acesso pelo backend via conexão Postgres dedicada;
- unique por conector, mercado e instante observado;
- histórico persistente validado em produção.

### Banco dedicado

Nunca usar o `DATABASE_URL` principal para observações do Radar. O banco dedicado usa:

```text
REAL_OPPORTUNITY_DATABASE_URL
```

Módulo:

```text
backend/app/real_markets/opportunity_database.py
```

Ele possui metadata, engine e session factory próprios.

---

## 5. Fases concluídas

### 9E — baseline

- 443 testes;
- commit `0969fd1`;
- tag `phase-9e-baseline`.

### 9F — Shadow Runtime

- simulação Shadow;
- scheduler opt-in;
- execução financeira desativada;
- 455 testes;
- feature `898d74d`;
- merge `54e0ed5`;
- tag `phase-9f-shadow-runtime`.

### 9G — soak/observabilidade Shadow

- script de soak;
- métricas;
- nove testes;
- 464 testes;
- merge `8769400`;
- tag `phase-9g-shadow-soak-observability`.

### 10A — Hyperliquid account read-only

Endpoint:

```text
GET /connectors/hyperliquid/account/{user}
```

Leituras por `/info`:

- role;
- clearinghouse state;
- spot state;
- open orders;
- fills;
- portfolio.

Sem signing, private key, `/exchange` ou envio de ordens.

Tag: `phase-10a-hyperliquid-account-readonly`.

### 10B — Hyperliquid testnet guardrails

- fail-closed;
- sem adapter real;
- sem signing;
- sem chave privada;
- tag `phase-10b-hyperliquid-testnet-guardrails`.

### 11 — Web MVP

- Dockerfile;
- `.dockerignore`;
- `railway.json`;
- deploy Render;
- health online;
- execução real desativada.

### 12A — hardening público

- `/health` público reduzido;
- health interno apenas em DEBUG;
- CORS fail-closed;
- 521 testes;
- tag `phase-12a-public-api-hardening`.

### 12B — dashboard

- dashboard online;
- portfólio Paper;
- navegação;
- oportunidades;
- correções visuais.

### 13A — Supabase foundation

Migration:

```text
supabase/migrations/20260730015700_phase13a_auth_foundation.sql
```

Criados: `profiles`, `audit_events`, RLS, policies, funções, triggers e primeiro admin com MFA obrigatório.

### 13B — autenticação/MFA

Implementado:

- JWT/JWKS Supabase;
- cookies HttpOnly;
- login, refresh, `/me`, logout;
- roles viewer/operator/admin;
- usuário ativo;
- recuperação e atualização de senha;
- TOTP/MFA/AAL2;
- WebSocket auth;
- frontend de login/reset/MFA.

Validação: 622 testes.

```text
d950a5d feat: secure dashboard with Supabase auth and MFA
b27efff
phase-13b-dashboard-auth
```

### 14 — radar real

- Kalshi read-only;
- Polymarket público;
- comparação YES+NO;
- filtro de similaridade;
- endpoint `/real-markets/radar/opportunities`;
- dashboard Radar Real;
- nenhuma arbitragem lucrativa confirmada após custos.

```text
merge 4c5f215
tag phase-14-results-mvp
```

### 15 — monitoramento

- histórico em memória;
- tendências NEW/IMPROVING/WORSENING/STABLE;
- endpoint `/real-markets/radar/history`;
- Top 30 no dashboard.

```text
merge 9f2bcd9
tag phase-15-opportunity-monitoring
```

### 16 — cache e persistência

Implementado:

- TTL configurável;
- cache por configuração;
- single-flight;
- `force_refresh`;
- persistência Supabase;
- hidratação após reinício;
- histórico priorizando fonte persistente;
- banco dedicado de observações;
- fail-safe.

Migration:

```text
supabase/migrations/20260731003000_phase16_real_market_observations.sql
```

Commits/tags:

```text
cb16f53
84c8119
phase-16-persistent-monitoring

62a1b63
574d383
phase-16-observation-db-isolation-fix
```

Produção aprovada: Session Pooler, persistência, cache, histórico e banco principal preservados.

### 17 — coletor automático, implantada e validada em produção

Merge `823d84f`, tag `phase-17-background-radar-collector`, deploy automático no Render em 01/08/2026.

Implementado:

- coletor periódico;
- APScheduler;
- single-flight entre threads/event loops;
- snapshot em memória;
- endpoint de snapshot;
- endpoint de status;
- dashboard lendo snapshot;
- coleta por acesso removida do dashboard;
- configuração desativada por default;
- cooldown de `force_refresh` externo;
- autenticação no único endpoint que atinge upstream;
- 688 testes aprovados.

Endpoints:

```text
GET /real-markets/radar/snapshot            # público, lê memória
GET /real-markets/radar/collector/status    # público, lê memória
GET /real-markets/radar/opportunities       # exige require_dashboard_user
```

#### Guardrails de carga upstream

`/opportunities` é o único endpoint capaz de atingir Polymarket e Kalshi, então recebeu duas proteções:

1. **Autenticação.** Passou a exigir `require_dashboard_user`. É uma mudança de contrato: o endpoint era público desde a Fase 14. `/snapshot` e `/collector/status` seguem públicos porque apenas leem memória.

2. **Cooldown de `force_refresh`.** `RealOpportunityScanService` mantém `_last_forced_at` por `ConfigurationKey`. Um `force_refresh` externo dentro da janela é rebaixado para leitura de cache em vez de gerar coleta. O coletor automático chama `scan(..., bypass_cooldown=True)`, pois já é limitado pelo intervalo do scheduler.

O payload de `monitoring` ganhou três campos: `force_refresh_requested`, `force_refresh_applied` e `force_refresh_retry_after_seconds`.

A janela é consumida no momento da requisição, antes da coleta executar. Se o scan falhar, o cooldown já foi gasto. É deliberado e coerente com a regra fail-closed da seção 1.

Detalhe não óbvio pela leitura do código: `bypass_cooldown=True` pula a **verificação** do cooldown, mas ainda **grava** `_last_forced_at`. Como o coletor automático usa esse caminho a cada ciclo, um `force_refresh` externo logo após um ciclo é recusado. É o comportamento desejado — o dado acabou de ser atualizado de qualquer forma — e foi confirmado em produção.

#### Resultado da validação em produção (01/08/2026)

```text
coletor    enabled=true cycles=11 successes=11 failures=0 skipped=0
           last_status=READY  last_markets_priced=20
           ciclo leva ~16s num intervalo de 60s

snapshot   status=READY  served_from_snapshot=true
           snapshot_is_stale=false
           snapshot_configuration_match=true
           snapshot_max_age_seconds=180.0  (intervalo 60 x multiplicador 3)
           duas chamadas seguidas: cycles 11 -> 11, delta 0

historico  source=persistent  persistence_available=true  error=null
           pontos atravessaram os reinicios do dia

guardrail  force_refresh externo rebaixado para cache,
           retry_after decrescendo, cache_hit=true

flags      read_only e market_data_only true; execution_authorized,
           financial_execution, automatic_execution_authorized e
           order_submission_available false nos tres endpoints
```

Quando o snapshot reporta `CONFIGURATION_MISMATCH`, compare `snapshot_configuration` com `requested_configuration` antes de suspeitar de defeito: em geral significa que alguém chamou `/opportunities` com os defaults daquele endpoint (`limit=40`, `near=0.04`), que diferem dos do coletor. Resolve-se sozinho no ciclo seguinte.

### 18 — domínio cripto read-only

Implementada em 02/08/2026. Bounded context novo em `backend/app/crypto_arbitrage/`, sem tocar em nenhum módulo existente. A adição é puramente aditiva: 688 testes antes, 752 depois, nenhuma regressão.

Estrutura entregue:

```text
backend/app/crypto_arbitrage/
├── domain/
│   ├── enums.py       VenueKind, MarketType, InstrumentStatus, Side,
│   │                  OrderType, TimeInForce, StrategyType, RiskStatus,
│   │                  ExecutionMode, ConnectorState
│   ├── errors.py      hierarquia sob CryptoArbitrageError
│   ├── money.py       aritmetica Decimal
│   ├── symbols.py     normalizacao entre venues
│   ├── fees.py        FeeRate e FeeSchedule
│   └── models.py      Instrument, OrderBookSnapshot, Opportunity,
│                      ExecutionPlan, OrderIntent, Fill, RiskDecision,
│                      Balance, ConnectorHealth, VwapResult
├── connectors/
│   ├── base.py        Protocols read-only + TradingAdapter declarado
│   └── registry.py    registro fail-closed
└── mocks/
    └── public_cex.py  conector deterministico, sem rede
```

#### Decisões que valem conhecer

**`money.to_decimal` recusa `float` em vez de convertê-lo.** A seção 28 proíbe float em valores financeiros, mas uma conversão silenciosa cumpriria a letra e violaria o espírito: `Decimal(0.1)` carrega o erro de representação para dentro do domínio, e ele se propaga por VWAP, taxas e PnL sem deixar rastro. Passar float levanta `PrecisionError`.

**`FeeSchedule` nunca devolve default.** Taxa ausente ou expirada levanta `FeeUnknownError`. É a invariante 15 da seção 8 aplicada na estrutura de dados, não na chamada — não existe caminho em que uma taxa desconhecida vire zero.

**O registry recusa por capacidade, não por tipo.** `assert_no_execution_capability` inspeciona o objeto em busca de `submit_order`, `cancel_order`, `withdraw`, `sign_transaction` e afins. Qualquer objeto que apenas *pareça* capaz de executar é recusado, mesmo sem declarar o Protocol. `register_trading_adapter` existe e sempre levanta `ExecutionNotAuthorizedError`, para que quem procure o caminho da execução encontre a recusa explícita em vez de improvisar.

**Defaults fail-closed nos modelos.** `InstrumentStatus.UNKNOWN`, `RiskStatus.BLOCKED` e `RiskDecision(approved=False)` são os valores iniciais. `Opportunity.is_executable` e `ExecutionPlan.is_authorized` retornam `False` incondicionalmente nesta fase. `ExecutionPlan` recusa `ExecutionMode.LIVE` na própria validação do modelo.

**O book valida o que normalmente se assume.** Ordenação de bids e asks, mercado cruzado, timestamps com timezone e profundidade suficiente. Um book desordenado produziria VWAP incorreto em silêncio; aqui levanta `DomainValidationError`.

Verificações da fase:

```text
752 passed, 2 warnings
nenhum import de rede em crypto_arbitrage/
float presente apenas em docstrings e na guarda que o recusa
nenhuma flag financeira True em app/
```

### 19A — fundação de market data

Implementada em 02/08/2026. Primeiro incremento da Fase 19, em `backend/app/crypto_arbitrage/market_data/`. Lógica pura, sem rede: 752 testes antes, 799 depois.

```text
local_book.py   BookLevelChange, BookUpdate, SequenceMode,
                BookStats, LocalOrderBook
freshness.py    FreshnessPolicy, FreshnessVerdict,
                is_usable_for_pricing, milliseconds_between
latency.py      LatencyTracker
```

#### Decisões que valem conhecer

**`SequenceMode` em vez de um parser por venue.** Cada venue numera updates de um jeito, mas a lógica de livro é a mesma. `BookUpdate` é neutro e carrega `first_update_id`, `final_update_id` e `previous_update_id`; o modo descreve *como* validar a continuidade:

```text
STRICT_INCREMENT   final == ultimo + 1
RANGE              first <= ultimo + 1 <= final
PREVIOUS_MATCH     previous == ultimo
NONE               sem validacao, evitar
```

Os conectores da 19B traduzem seus payloads para esse formato. A escolha evita espalhar regra de sequência dentro da manutenção do book, e permitiu escrever a lógica antes de confirmar os formatos reais das três venues.

**Ignorado é diferente de rejeitado.** Update anterior ao snapshot é descartado com `False` e contado em `ignored_stale_updates`: durante a sincronização inicial isso é esperado, não é defeito. Já um buraco na sequência levanta `SequenceGapError` e marca o livro para resync. Confundir os dois casos geraria alarme falso na largada ou, pior, silêncio diante de perda real de mensagem.

**Book cruzado é corrupção, não oportunidade.** Se o melhor bid alcançar o melhor ask, `CorruptedBookError` é levantado e o livro exige resync. Um book local cruzado significa que a aplicação de deltas divergiu da venue — jamais que apareceu arbitragem. Corrigir localmente esconderia a divergência.

**`is_ready` exige snapshot presente *e* ausência de resync pendente.** `to_snapshot` recusa livro não pronto, então nenhum book degradado alimenta cálculo de oportunidade por descuido.

**O veredito de frescor carrega o motivo.** `FreshnessVerdict` devolve `is_fresh`, idade, limite e texto. "Por que esta oportunidade foi descartada" é a pergunta que se faz depois, e reconstruir isso a partir de um booleano é impossível.

**Idade negativa não é dado novo.** Timestamp adiantado além de `max_clock_skew_ms` invalida o dado: não se sabe mais qual relógio mentiu. O `LatencyTracker` preserva amostras negativas em vez de zerá-las, porque skew de relógio é sintoma real e escondê-lo com `max(0, x)` apagaria a evidência.

**Conector degradado bloqueia mesmo com book recente.** `is_usable_for_pricing` combina estado e frescor: idade baixa só prova que a última mensagem chegou há pouco, não que o livro reflete a venue.

### 19B — adaptadores Binance, OKX e Bybit

Implementada em 02/08/2026. Tradução dos formatos públicos das três venues para o domínio, em `backend/app/crypto_arbitrage/connectors/`. Sem rede: os adaptadores recebem `dict` já decodificado. 799 testes antes, 840 depois.

```text
connectors/venue_adapter.py   tipos comuns: SnapshotPayload, StreamMessage,
                              StreamMessageKind, InstrumentParseResult,
                              SkippedInstrument, VenueAdapter, parse_levels
connectors/binance/           BinanceSpotAdapter
connectors/okx/               OkxSpotAdapter
connectors/bybit/             BybitSpotAdapter
```

#### Formatos confirmados na documentação oficial em 02/08/2026

| Venue | Instrumentos | Book | Modo |
|---|---|---|---|
| Binance | `/api/v3/exchangeInfo` | `/api/v3/depth`, stream `depthUpdate` | `RANGE` |
| OKX | `/api/v5/public/instruments` | canal `books` | `PREVIOUS_MATCH` |
| Bybit | `/v5/market/instruments-info` | tópico `orderbook.<depth>.<symbol>` | `MONOTONIC` |

#### A Bybit tem garantia de integridade mais fraca

Isto é achado de pesquisa, não limitação da implementação, e deve pesar no buffer de segurança do scanner da Fase 20.

A documentação da Bybit **não afirma** que `u` incrementa de um em um entre deltas, **não descreve** método para detectar mensagem perdida, e diz que `seq` serve para comparar níveis de profundidade entre si — não para achar buraco. Pior: em nível 1, o snapshot é reenviado com o **mesmo** `u` quando nada muda por três segundos.

Presumir `STRICT_INCREMENT` inventaria uma garantia inexistente e produziria alarme falso de gap em operação normal. Daí o modo `MONOTONIC`, acrescentado ao 19A: exige apenas que a sequência avance, sem alegar detecção de gap. A integridade da Bybit fica por conta do que ela de fato documenta — `type == "snapshot"` obriga reset, `u == 1` indica reinício de serviço e também obriga reset, e o livro levanta erro se cruzar.

Binance e OKX detectam gap de verdade. Bybit não.

#### O checksum da OKX foi depreciado

Em **23/06/2026** a OKX depreciou o campo `checksum` dos canais `books`, `books-l2-tbt` e `books50-l2-tbt`. O campo continua presente, mas com valor **fixo em `0`**, e a documentação diz explicitamente que não deve mais ser usado para verificar integridade. A orientação oficial passou a ser `seqId`/`prevSeqId`.

Consequência prática: não há trabalho de CRC32 a fazer. Versões anteriores do planejamento previam esse esforço; ele deixou de existir.

#### Outras decisões

**`parse_levels` lê por posição fixa.** A OKX publica quatro elementos por nível; os dois últimos não interessam ao livro. Ignorar o excedente mantém um parser único válido para as três venues.

**Descarte de instrumento carrega o motivo.** `InstrumentParseResult` separa aceitos de descartados, e cada descarte traz `raw_symbol` e razão. Um símbolo malformado não derruba a lista inteira, mas também não some em silêncio — sumir viraria "a venue não lista esse par" na investigação seguinte.

**`StreamMessageKind.IGNORED` é explícito.** Confirmação de inscrição, ping e mensagens de controle devolvem um tipo próprio em vez de `None`, obrigando quem consome a decidir o que fazer em vez de tratar ausência como sucesso.

**Cuidado documentado da Binance:** o campo `pu` existe na API de **futuros** USDS-M, não no spot. Validar contra ele no spot compararia com campo inexistente. `is_snapshot_usable` implementa o passo 4 do procedimento oficial: snapshot com `lastUpdateId` menor que o `U` do primeiro evento bufferizado é velho demais e outro precisa ser buscado.

### 19C1 — orquestração de stream

Implementada em 02/08/2026. Terceiro incremento da Fase 19, ainda sem rede: contratos de transporte, política de reconexão, rate limit, métricas e o orquestrador que junta tudo. 840 testes antes, 880 depois.

```text
connectors/transport.py         RestTransport, WebSocketTransport (Protocols)
market_data/backoff.py          BackoffPolicy, ReconnectTracker
market_data/rate_limiter.py     TokenBucketRateLimiter
market_data/metrics.py          ConnectorMetrics
market_data/stream_manager.py   BookStreamManager, StreamOutcome, StreamResult
```

O 19C foi dividido porque transporte concreto e orquestração são riscos diferentes. A orquestração é onde erros custam caro e é totalmente testável sem rede; o cliente HTTP e o WebSocket são encanamento. O 19C2 entrega os clientes concretos com `httpx` e `websockets`, ambos já presentes no `requirements.txt` — a fase não acrescenta dependência.

#### Decisões que valem conhecer

**Gap e corrupção viram resultado, não exceção.** `handle_message` devolve `StreamResult` com `StreamOutcome`, e `RESYNC_REQUIRED` cobre gap de sequência, book cruzado e delta antes do snapshot. São estados operacionais previstos, não bugs. Deixá-los escapar como exceção obrigaria cada chamador a reimplementar o mesmo `try/except`, e bastaria um esquecimento para uma perda de mensagem virar crash — ou, pior, ser engolida.

**A aleatoriedade do jitter é parâmetro, não chamada interna.** `delay_for(attempt, random_value=...)` recebe o sorteio de fora. Uma política de reconexão que não pode ser reproduzida num teste é uma política que ninguém consegue auditar depois de um incidente.

**O jitter só reduz o atraso.** Nunca ultrapassa o teto configurado. Estourar o máximo por causa de sorteio seria surpresa desnecessária justamente durante uma queda.

**`ReconnectTracker.reset()` é explícito.** Só deve ser chamado depois de a conexão provar que funciona — tipicamente após o primeiro snapshot aplicado. Zerar já na conexão faria uma queda em laço parecer eternamente a primeira tentativa, e o backoff nunca escalaria.

**O relógio do rate limiter é injetado.** Um limitador que só pode ser testado esperando de verdade não é testado. O balde também tolera relógio andando para trás: realinha a referência em vez de repor tokens indevidamente.

**Rate limit local é preventivo, não substituto.** Ser bloqueado pela venue custa muito mais do que esperar localmente — costuma vir com banimento temporário de IP, e nesse intervalo o book inteiro para de atualizar.

**Saúde olha o estado atual, não o histórico.** `ConnectorMetrics.is_healthy` depende de `ConnectorState`, não dos contadores. Um gap resolvido por resync há uma hora não deve manter o conector marcado como doente para sempre.

**`snapshot_for_pricing` devolve snapshot e veredito juntos.** Livro não pronto ou velho demais devolve `None` com o motivo. Quem chama não reimplementa a decisão e não tem como esquecer de checá-la.

**Reconexão obriga resync.** `mark_disconnected` invalida o livro: mensagens perdidas enquanto o socket esteve fora não têm como ser recuperadas, e o livro local deixou de refletir a venue.

### 19C2 — transportes concretos e sincronização inicial

Implementada em 02/08/2026. Quarto incremento da Fase 19. 880 testes antes, 912 depois. Nenhuma dependência nova: `httpx` e `websockets` já estavam no `requirements.txt`.

```text
connectors/http_transport.py       HttpxRestTransport
connectors/websocket_transport.py  WebsocketsTransport
market_data/synchronizer.py        BookSynchronizer, SyncState, SyncStats
pytest.ini                         marcador integration, desligado por default
```

#### O procedimento de sincronização é o núcleo deste incremento

É aqui que books locais divergem em silêncio, e a causa é quase sempre a mesma: buscar o snapshot **antes** de abrir o stream perde tudo o que acontece entre as duas coisas, e o livro nasce errado sem emitir sinal algum.

A ordem correta é o inverso:

```text
1. abrir o stream e BUFFERIZAR os deltas
2. so entao buscar o snapshot REST
3. conferir se o snapshot alcanca o primeiro delta bufferizado
4. aplicar o snapshot
5. reproduzir o buffer, descartando o que ja estava contido
6. passar para modo ao vivo
```

**O passo 3 é o que a maioria das implementações esquece.** Snapshot antigo demais deixa um vão entre ele e o buffer, e esse vão nunca é preenchido. `apply_rest_snapshot` recusa em vez de aplicar: livro que nasce com vão é pior do que livro que ainda não existe, porque parece pronto.

`BookSynchronizer` implementa isso como máquina de estados — `BUFFERING`, `SYNCED`, `FAILED` — e usa `is_snapshot_usable` quando o adaptador oferece, caindo numa comparação genérica de sequência quando não.

**A fila é limitada.** Buffer sem teto em processo de vida longa é vazamento de memória disfarçado, e buffer gigante já é sinal de que a sincronização travou. Estourar leva a `FAILED` e exige recomeço — melhor do que acumular.

**Venue que empurra snapshot dispensa o REST.** A Bybit envia `type: "snapshot"` logo na inscrição; nesse caso o sincronizador aplica direto e passa a `SYNCED` sem nunca chamar o endpoint REST.

#### Decisões dos transportes

**O cliente httpx é injetado, nunca criado internamente.** Quem constrói decide timeout, proxy e limites de conexão. Nos testes entra `httpx.MockTransport`, que percorre o caminho real de parsing sem abrir socket.

**Rate limit local recusa antes de gastar a cota da venue.** Há teste específico provando que a requisição bloqueada **não chega** ao handler. E `429` vindo da venue vira `RateLimitExceededError`, contabilizado como rate limit e não como erro genérico — são causas diferentes e levam a ações diferentes.

**A conexão WebSocket é injetável e o import de `websockets` é tardio.** A API pública da biblioteca mudou de lugar entre versões; isolar o import num único ponto evita que uma atualização quebre a importação do pacote inteiro.

**`ping_interval` e `ping_timeout` são explícitos.** Conexão de market data que morre em silêncio é pior do que conexão que cai: sem heartbeat, o livro local continua parecendo saudável enquanto para de receber atualização.

**`float` aparece apenas em timeouts.** `ping_interval`, `ping_timeout` e `open_timeout` são parâmetros de tempo exigidos pela biblioteca. A proibição da seção 28 é sobre valor financeiro — preço, quantidade, taxa, PnL, saldo —, e nenhum deles usa float em lugar nenhum do domínio.

#### Testes de integração

`pytest.ini` passou a registrar o marcador `integration` e a desligá-lo por padrão via `addopts = -ra -m "not integration"`. Testes que toquem rede devem ser marcados e só rodam sob pedido explícito:

```powershell
.venv\Scripts\python.exe -m pytest -m integration
```

Assim eles existem e ficam documentados sem violar a regra da seção 28, que exige que a suíte padrão não dependa de internet.

### 20A — scanner CEX-CEX Paper

Implementada em 02/08/2026. Motor de lucratividade e scanner espacial entre venues, em `backend/app/crypto_arbitrage/opportunities/`. Lógica pura. 912 testes antes, 939 depois.

```text
opportunities/profitability.py   CostModel, ProfitBreakdown,
                                 compute_breakdown, meets_thresholds,
                                 resolve_taker_rates
opportunities/cex_cex.py         CexCexScanner, ScanReport,
                                 ScoredOpportunity, RejectedRoute
```

#### Decisões que valem conhecer

**Pares ordenados, não combinações.** Comprar na A e vender na B é uma oportunidade diferente de comprar na B e vender na A — profundidades e custos são próprios de cada direção. O scanner avalia as duas e rejeita a que não fecha, registrando o motivo.

**Toda rejeição carrega motivo e estágio.** `RejectedRoute` marca `freshness`, `depth`, `fees`, `profitability` ou `modelling`. "Não achei nada" é resposta inútil quando se investiga por que o sistema ficou parado a manhã inteira; "book da OKX stale há 4s" e "taxa da Bybit desconhecida" levam a ações diferentes.

**Frescor é filtrado antes de qualquer cálculo.** Não adianta calcular VWAP de book que seria rejeitado no fim, e a ordem deixa a invariante 14 evidente no código.

**Reservas incidem sobre o notional, não sobre o lucro.** `slippage_ratio` e `safety_buffer_ratio` multiplicam o valor negociado. O risco de execução acompanha o tamanho da posição, não o do ganho projetado — amarrar reserva ao lucro esperado faria a proteção encolher justamente quando a margem é fina.

**Taker nas duas pontas por padrão.** `resolve_taker_rates` não considera maker: contar com maker exige repousar ordem no livro, e o preço pode sumir antes do fill. É a hipótese conservadora.

**`ProfitBreakdown` guarda cada parcela.** VWAPs, taxas por perna, reserva de slippage, buffer, lucro e ROI. Guardar só o total impediria responder depois por que uma oportunidade foi descartada, ou por que o realizado divergiu do esperado.

Nota sobre o encaixe com a Fase 18: `Opportunity` tem uma única reserva (`safety_buffer`). O scanner soma slippage e buffer operacional ali, e a separação detalhada fica no `ProfitBreakdown` anexo ao `ScoredOpportunity`. Se um dia a separação precisar viajar junto do modelo, é o `Opportunity` que muda.

**Nada disso executa.** As oportunidades nascem com `RiskStatus.BLOCKED`, `is_executable` falso, e o payload declara todas as flags financeiras como falsas.

#### O que a 20A ainda não faz

Falta o **20B**: expor o scanner por API e no dashboard, e alimentá-lo com books reais vindos do `BookSynchronizer`. Até lá o `crypto_arbitrage` segue biblioteca pura, sem roteador, job ou endpoint.

Também ficam para depois, por dependerem de conta privada ou de execução: taxas efetivas por conta em vez de tabela configurada (Fase 25), reserva de saldo e inventário (seção 16), e qualquer forma de execução (Fases 26 e 27).

### Fumaça de integração contra as venues reais

Adicionada em 02/08/2026, em `backend/tests/test_integration_venue_smoke.py`.

Motivo: as Fases 18 a 20A foram construídas sobre fixtures escritas a partir da documentação. Nenhuma linha daquele código tinha visto resposta real de venue. Documentação e realidade divergem em detalhes que quebram parser, e o custo de descobrir isso cresce a cada camada empilhada em cima.

Todos os testes estão marcados com `integration` e ficam **fora da suíte padrão**. Somente endpoints públicos: nenhuma credencial, nenhuma chave, nenhuma ordem.

```powershell
.venv\Scripts\python.exe -m pytest -m integration -v
```

Resultado da primeira execução, **10/10 em ~32s, sem exigir nenhum ajuste nos adaptadores**:

```text
REST        Binance, OKX e Bybit: instrumentos e book parseiam,
            livro monta, VWAP calcula, bid < ask.
            Nenhum instrumento descartado por filtro ausente.

WebSocket   Binance: depthUpdate reconhecido; sincronizador segue
                     em BUFFERING, correto, porque a Binance nao
                     empurra snapshot e depende do REST.
            OKX:     empurra snapshot na inscricao -> SYNCED.
            Bybit:   empurra snapshot na inscricao -> SYNCED,
                     deltas aplicados, livro nao cruzado.
```

#### Medição pendente: o `u` da Bybit incrementa de 1

Um diagnóstico à parte, sobre 39 mensagens de `orderbook.50.BTCUSDT`, mediu os saltos do campo `u`:

```text
saltos de u:   [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
todos == 1:    True
algum == 0:    False
algum > 1:     False
```

Isso contradiz parcialmente a conclusão da 19B, que escolheu `MONOTONIC` por a documentação não prometer incremento de 1. Na prática ela incrementa.

Mais relevante: as duas exceções que a documentação descreve **já são tratadas antes da validação de sequência**.

| Exceção documentada | Onde já é tratada |
|---|---|
| `u == 1` (reinício de serviço) | O adaptador converte em `SNAPSHOT` |
| Mesmo `u` reenviado (nível 1 sem mudança) | `final <= last` → ignorado como replay |

Ou seja, `STRICT_INCREMENT` provavelmente daria à Bybit detecção real de gap — que hoje ela não tem — sem os alarmes falsos que motivaram `MONOTONIC`.

**Decisão em 02/08/2026: manter `MONOTONIC` por ora.** A amostra é pequena (39 mensagens, um par, trinta segundos), e a Bybit funciona hoje com as demais proteções: snapshot novo obriga reset, `u == 1` obriga reset, e book cruzado levanta `CorruptedBookError`.

Ao revisitar, pesar a assimetria dos erros:

- **falso positivo** (resync desnecessário) custa uma busca de snapshot; é visível e recuperável;
- **falso negativo** (gap não detectado) corrompe o livro em silêncio e faz o scanner produzir oportunidade fantasma.

A filosofia fail-closed do projeto prefere a falha visível, o que favorece a troca. Falta evidência de produção sobre regimes de mercado com mais volume. A mudança é uma linha em `connectors/bybit/spot_adapter.py`.

### 20B — coletor do scanner cripto

Implementada em 02/08/2026. 939 testes antes, 965 depois. **É aqui que o `crypto_arbitrage` deixa de ser biblioteca pura**: passa a ter job de scheduler e configuração própria.

```text
services/book_source.py       RestBookSource
services/scanner_service.py   CryptoScannerService
services/factory.py           build_scanner_service, get_scanner_service
connectors/*/spot_adapter.py  +instrument_id_for, +depth_request
core/settings.py              14 variaveis CRYPTO_SCANNER_*
scheduler/tasks.py            +crypto_scanner_background_task
core/application.py           registro condicional do job
```

#### A decisão mais importante: REST, não WebSocket, em produção

O WebSocket está implementado, testado e validado contra as venues reais. Mesmo assim o coletor usa **REST periódico**.

O motivo é a hospedagem. A seção 4 registra que o processo no Render Free dorme e reinicia. Socket persistente em processo que hiberna significa reconexão constante, e cada reconexão obriga resync completo — o livro nunca alcança estado estável, e o custo é maior que o benefício.

A seção 14 afirma que REST periódico não serve como hot path de arbitragem, e **isso continua verdade para execução**. A Fase 20 é Paper: o objetivo é descobrir se existe ineficiência líquida, não capturá-la. Latência de polling não impede essa resposta, e nenhuma decisão de execução depende dela.

Quando houver hospedagem que não hiberne, `BookSynchronizer` e `WebsocketsTransport` já estão prontos para assumir sem mudança de domínio.

#### Outras decisões

**Falha parcial não derruba o ciclo.** Uma venue fora do ar some do conjunto e fica registrada em `last_venue_errors`; as demais continuam sendo comparadas. "O scanner não achou nada" e "a OKX está fora" pedem ações diferentes.

**Ler não coleta.** `snapshot()` devolve o último relatório sem disparar coleta, com teste específico provando que chamadas repetidas não tocam as venues. É a lição da Fase 17: coleta por acesso deixa a carga upstream proporcional ao tráfego do dashboard, não ao intervalo configurado.

**Single-flight com `Lock` de thread, não `asyncio.Lock`.** O BackgroundScheduler roda o job em thread própria, e a seção 28 proíbe compartilhar lock de asyncio entre loops.

**O book de REST passa pelo `LocalOrderBook`.** Em vez de montar o snapshot direto, `RestBookSource` aplica o payload num livro local. Assim o dado de REST recebe as mesmas validações do dado de stream — ordenação, mercado cruzado, níveis positivos. Um book cruzado vindo da venue levanta erro em vez de virar oportunidade.

**Taxas vêm de configuração versionada.** `CRYPTO_SCANNER_TAKER_FEES` no formato `VENUE:taxa`. A seção 9 proíbe hardcode, e a Fase 25 é que traz taxa efetiva por conta. Com o scanner ligado, **venue sem taxa configurada impede o boot** — é a invariante 15 aplicada na validação de settings.

**A fábrica constrói sob demanda.** Importar o módulo não abre cliente HTTP nem lê configuração. O boot deve falhar por validação de `settings`, não por efeito colateral de import.

#### Configuração da Fase 20B

Defaults, todos seguros:

```text
CRYPTO_SCANNER_ENABLED=false
CRYPTO_SCANNER_INTERVAL_SECONDS=60
CRYPTO_SCANNER_VENUES=BINANCE,OKX,BYBIT
CRYPTO_SCANNER_BASE_ASSET=BTC
CRYPTO_SCANNER_QUOTE_ASSET=USDT
CRYPTO_SCANNER_QUANTITY=0.01
CRYPTO_SCANNER_DEPTH=50
CRYPTO_SCANNER_MAX_BOOK_AGE_MS=5000
CRYPTO_SCANNER_SLIPPAGE_RATIO=0.0005
CRYPTO_SCANNER_SAFETY_BUFFER_RATIO=0.0005
CRYPTO_SCANNER_MINIMUM_NET_PROFIT=0
CRYPTO_SCANNER_MINIMUM_ROI=0
CRYPTO_SCANNER_TAKER_FEES=BINANCE:0.001,OKX:0.001,BYBIT:0.001
CRYPTO_SCANNER_REQUEST_TIMEOUT_SECONDS=10
CRYPTO_SCANNER_RATE_LIMIT_CAPACITY=10
CRYPTO_SCANNER_RATE_LIMIT_REFILL_PER_SECOND=5
```

Valores decimais ficam como `str` de propósito: o domínio cripto recusa `float` em valor financeiro.

Validações fail-closed no boot: intervalo 30–3600; profundidade 1–500; idade de book 100–600000 ms; ratios 0–0.25; ROI 0–1; taxas 0–0.25; base e quote diferentes; e, com o scanner ligado, ao menos **duas** venues (arbitragem espacial compara venues) e taxa configurada para **todas** elas.

O job só é registrado quando `SCHEDULER_ENABLED` e `CRYPTO_SCANNER_ENABLED` são verdadeiros.

#### O que falta

Nada: o **20C** (API) e o **20D** (painel) foram entregues em seguida.

### 20C — API do scanner cripto

Implementada em 02/08/2026. 965 testes antes, 981 depois.

```text
api/routers/crypto_scanner.py   GET /crypto/scanner/snapshot
                                GET /crypto/scanner/status
core/application.py             registro do roteador
```

**Os endpoints nascem exigindo `require_dashboard_user`**, e a dependência fica **no roteador**, não rota a rota — assim endpoints futuros nascem protegidos por construção, sem depender de alguém lembrar.

A razão está registrada porque custou caro aprender: o `/real-markets/radar/opportunities` da Fase 14 nasceu público, e quando a proteção veio na Fase 17 ela virou um no-op em produção, porque a flag que a ativava estava desligada. Fechar depois consumiu uma manhã inteira; abrir depois é trivial.

**Coletor desligado devolve 200 com `status: DISABLED`, não erro.** Desligado é configuração válida, e quem consome precisa distinguir "não configurado" de "configurado e sem oportunidade". Há teste garantindo que, nesse estado, o serviço **nem chega a ser construído** — e outro garantindo que a autenticação continua exigida mesmo desligado, para não vazar estado de configuração.

Nenhum endpoint dispara coleta: todos leem o snapshot em memória.

#### Duas armadilhas de teste encontradas aqui

Valem registro porque vão reaparecer.

**O `.env` local liga a autenticação.** `AUTH_ENABLED` e `AUTH_REQUIRED_FOR_DASHBOARD` estão verdadeiros no `.env` de desenvolvimento, então testes que esperam 200 falham se não desligarem a exigência explicitamente. Teste que depende de configuração de ambiente passa ou falha conforme a máquina. Cada teste deve declarar o que precisa, e os fixtures `client` e `enforcing_client` fazem isso.

**`app.routes` não achata mais rotas incluídas.** O FastAPI 0.139 embrulha roteadores num `_IncludedRouter`, então varrer `app.routes` procurando caminho não encontra nada — mesmo com a rota funcionando. Para verificar registro, inspecione `router.routes` ou faça uma requisição e confira que não é 404.

### 20D — painel do scanner cripto no dashboard

Implementada em 03/08/2026, na branch `feature/phase-20d-crypto-dashboard`. Fecha a Fase 20. 981 testes antes, 996 depois.

```text
dashboard/templates/dashboard.html          +142  painel e navegação
dashboard/static/js/dashboard.js            +468  render, fetch, estados
dashboard/static/css/dashboard.css           +55  alertas, rejeições
tests/test_phase20d_crypto_dashboard.py      +15 testes
```

O painel consome `/crypto/scanner/snapshot` e `/crypto/scanner/status`, e exibe métricas do coletor, tabela de rotas com a decomposição de custos do `ProfitBreakdown`, rotas rejeitadas com motivo e estágio, e erros por venue.

#### Decisões que valem conhecer

**O painel nunca dispara coleta.** Só lê os dois endpoints de memória, e há teste travando isso — `force_refresh`, `POST` e qualquer rota de scan são proibidos no bloco cripto do script. É a lição da Fase 17 aplicada ao front: coleta por acesso liga a carga upstream ao tráfego do dashboard, e não ao intervalo configurado.

**`401` e `403` têm mensagem própria, separada de falha do scanner.** Os endpoints cripto exigem `require_dashboard_user`, ao contrário de `/real-markets/radar/snapshot`, que é público. Uma sessão sem MFA recebe "sessão expirada ou sem MFA", não "não foi possível atualizar". Colapsar as duas causas reproduziria no painel o defeito de mensagem única já registrado para o login na seção 4 — o mesmo erro, na mesma base de código, duas vezes.

**Alertas de venue não reutilizam `.real-radar-alerts`.** Aquela classe é verde porque sinaliza oportunidade encontrada. Usá-la para "a OKX não respondeu" pintaria um erro de verde e comunicaria o oposto do que aconteceu. Daí `.crypto-scanner-alerts`, em âmbar. A reutilização de CSS é barata; a inversão de significado, não.

**Scanner desligado renderiza como configuração, não como erro.** `status: "DISABLED"` mostra "Scanner desligado" e o `detail` do backend. É o estado atual em produção, então é o primeiro que qualquer pessoa vê — um painel que parece quebrado nesse estado geraria investigação inútil.

**A falha do `/status` não apaga o painel.** O snapshot é a informação principal; o status é complementar. Se o segundo falhar, o painel mostra `STATUS_INDISPONÍVEL` nos contadores e preserva a tabela de rotas.

#### Regressão de encoding corrigida junto

`DASHBOARD_VIEWS` continha literalmente `"Vis?o Geral"` e `"Posi??es"` — mojibake antigo, anterior a esta fase. Como `dashboard.js:727` usa esse valor como título visível da página, o defeito estava na tela. Corrigido, com teste de regressão; nenhum teste dependia das strings quebradas.

Cuidado para o futuro: `dashboard.js` **é UTF-8 válido e sem BOM**, e acentos diretos funcionam — boa parte do arquivo já os usa. Os escapes `ç` do bloco do Radar são hábito, não exigência. Antes de assumir que o arquivo não aceita acento, verifique com `[System.IO.File]::ReadAllText` e um `UTF8Encoding` estrito.

#### Como validar sem executar JavaScript

A suíte não roda JS, então o contrato do front é verificado sobre o próprio fonte, como nas fases 12B, 14, 15 e 17. É rasteiro de propósito: pega remoção acidental de `id`, troca de endpoint e regressão de encoding, que são os defeitos que de fato ocorreram aqui. Para sintaxe, `node --check` cobre o que os testes não cobrem.

As asserções negativas são escopadas ao bloco cripto (`JS.split("const cryptoScannerState")[-1]`) para que um `POST` legítimo em outro painel não quebre esta fase.

---

## 6. Configurações da Fase 17

Defaults:

```text
REAL_OPPORTUNITY_BACKGROUND_COLLECTOR_ENABLED=false
REAL_OPPORTUNITY_BACKGROUND_INTERVAL_SECONDS=60
REAL_OPPORTUNITY_BACKGROUND_LIMIT_PER_CONNECTOR=20
REAL_OPPORTUNITY_BACKGROUND_FEE_BUFFER=0.02
REAL_OPPORTUNITY_BACKGROUND_NEAR_THRESHOLD=0.05
REAL_OPPORTUNITY_BACKGROUND_CONCURRENCY=8
REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER=3
REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS=30
```

Validações:

- intervalo: 30–3600;
- limite: 1–100;
- fee/near threshold: 0–0.25;
- concorrência: 1–20;
- multiplicador de idade do snapshot: 1–10;
- cooldown de force refresh: 0–3600, sendo `0` desativação total;
- coletor exige `SCHEDULER_ENABLED=true`.

Ativação futura no Render, somente depois de commit/merge/deploy autorizados:

```text
REAL_OPPORTUNITY_BACKGROUND_COLLECTOR_ENABLED=true
REAL_OPPORTUNITY_BACKGROUND_INTERVAL_SECONDS=60
REAL_OPPORTUNITY_BACKGROUND_LIMIT_PER_CONNECTOR=20
REAL_OPPORTUNITY_BACKGROUND_FEE_BUFFER=0.02
REAL_OPPORTUNITY_BACKGROUND_NEAR_THRESHOLD=0.05
REAL_OPPORTUNITY_BACKGROUND_CONCURRENCY=8
REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER=3
REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS=30
```

Persistência existente:

```text
REAL_OPPORTUNITY_PERSISTENCE_ENABLED=true
REAL_OPPORTUNITY_DATABASE_URL=<SESSION POOLER SECRET>
REAL_OPPORTUNITY_PERSISTENCE_HISTORY_LIMIT=60
REAL_OPPORTUNITY_CACHE_TTL_SECONDS=45
```

---

## 7. Arquitetura atual

### API

```text
backend/app/core/application.py
backend/app/main.py
backend/app/api/routers/
```

### Configurações

```text
backend/app/core/settings.py
```

Toda configuração nova deve ter default seguro e validação fail-closed.

### Scheduler

```text
backend/app/scheduler/scheduler.py
backend/app/scheduler/tasks.py
```

APScheduler:

```text
coalesce=true
max_instances=1
misfire_grace_time=30
```

Jobs conhecidos:

```text
market_update_task
shadow_runtime_task
real_opportunity_background_task
```

### Event bus

```text
backend/app/events/event.py
backend/app/events/event_bus.py
backend/app/events/listener.py
```

Evento conhecido: `market.updated`.

### Conectores

```text
backend/app/connectors/
backend/app/real_markets/
```

Existentes: Mock, Hyperliquid read-only, Polymarket e Kalshi.

### Paper/Shadow

```text
backend/app/paper/
```

Objetivos: simular, auditar e validar sem modificar saldo real.

### Dashboard

```text
backend/app/dashboard/templates/dashboard.html
backend/app/dashboard/static/js/dashboard.js
```

Exibe autenticação, status, portfólio Paper, oportunidades, Radar Real, tendências e snapshot.

---

## 8. Invariantes de segurança

Estas flags devem permanecer falsas fora de uma futura execução explicitamente autorizada:

```text
paper_execution_authorized
live_authorization
execution_authorized
live_execution
financial_execution
next_step_authorized
automatic_execution_authorized
order_submission_available
wallet_signing
private_key_access
credential_access
exchange_endpoint_available
```

Regras:

1. Dados reais podem ser usados em modo read-only.
2. Shadow não modifica Paper.
3. Paper não modifica conta real.
4. Testnet não autoriza mainnet.
5. API key não implica permissão de trade.
6. Permissão de trade não implica saque.
7. Saque deve permanecer desativado para robôs.
8. Chaves de leitura e execução devem ser separadas.
9. Browser nunca recebe secrets.
10. Erro parcial entre pernas exige contenção/reconciliação.
11. IA não autoriza sozinha uma ordem.
12. Toda ordem precisa de `client_order_id` idempotente.
13. Quote DEX expirada não pode ser executada.
14. Book stale não pode gerar ordem.
15. Taxa desconhecida invalida a oportunidade.
16. Saldo não reservado invalida o plano.

---

## 9. Nova missão: arbitragem cripto CEX/DEX/Web3

### Objetivo

Criar um novo domínio capaz de:

- receber livros e trades em tempo real;
- normalizar mercados de diferentes venues;
- calcular preços executáveis por profundidade;
- considerar todos os custos;
- detectar ineficiências;
- simular execução;
- acompanhar resultados;
- operar em testnet;
- futuramente executar operações reais pequenas e controladas.

### Critérios de seleção de venues

Avaliar:

- liquidez e profundidade;
- estabilidade/latência de API;
- WebSocket;
- sequence/checksum;
- rate limits;
- maker/taker efetivos;
- testnet;
- disponibilidade regional;
- precisões, mínimos e status de instrumentos;
- depósitos/saques;
- subcontas;
- escopos de API;
- capacidade de desativar saque;
- eventos privados de ordem/fill.

### CEXs solicitadas

| CEX | Liquidez de planejamento | Taxa de referência fornecida | Uso pretendido |
|---|---:|---:|---|
| Binance | máxima | 0,1% ou menos | alto volume e pares |
| OKX | alta | 0,08% / 0,1% | API V5 |
| Bybit | alta | 0,1% | spot/derivativos |
| Kraken | média/alta | 0,16% / 0,26% | estabilidade |
| Coinbase | alta | variável | mercado institucional |
| KuCoin | média | 0,1% | altcoins |

Esses valores são apenas entradas de planejamento. Não hardcode taxas. Elas variam por conta, tier, produto, par, região, maker/taker e descontos. Consultar a taxa efetiva da conta ou usar configuração versionada e conservadora.

### Web3 solicitada

| Ecossistema | Protocolos | Papel |
|---|---|---|
| Ethereum/L2 | Uniswap, Curve, 1inch | DEX/agregação |
| Solana | Jupiter, Raydium | agregação/DEX |
| BNB Smart Chain | PancakeSwap | DEX/roteamento |
| Multi-chain | LayerZero, Stargate | mensageria/transporte |

### Prioridade recomendada

1. Binance, OKX e Bybit — dados públicos.
2. Scanner CEX-CEX Paper.
3. Kraken, Coinbase e KuCoin.
4. Jupiter e 1inch read-only.
5. CEX-DEX Paper.
6. Integrações diretas Uniswap, Curve, Raydium e PancakeSwap.
7. Cross-chain por último.

Cross-chain não deve entrar inicialmente no hot path. Preferir inventário pré-financiado e rebalanceamento separado.

---

## 10. Estratégias alvo

### CEX-CEX espacial

```text
Comprar BTC/USDT na CEX A
Vender BTC/USDT na CEX B
```

Requisitos:

- saldo pré-posicionado;
- execução sem esperar transferência;
- VWAP por profundidade;
- leg risk;
- fills parciais;
- reconciliação.

### Triangular em uma CEX

```text
USDT -> BTC -> ETH -> USDT
```

Requisitos: três books sincronizados, taxas por perna, mínimos, rounding conservador e plano de compensação.

### CEX-DEX

```text
Comprar na CEX
Vender via Jupiter ou 1inch
```

Considerar inventário, quote válida, gas/priority fee, slippage, MEV, tempo de inclusão, falha e hedge.

### DEX-DEX mesma chain

Idealmente atômica:

- rotas na mesma transação;
- revert se lucro mínimo não for atingido;
- simulação RPC;
- quote/deadline;
- gas;
- proteção MEV.

Pode exigir contrato próprio, auditoria e fork tests.

### Spot-perp / cash-and-carry

Módulo separado:

```text
long spot
short perpetual
captura de basis/funding
```

Modelar funding, margem, liquidação, borrow e hedge ratio.

### Cross-chain

Inicialmente apenas rebalanceamento. Só avaliar arbitragem direta após medir tempo, taxa, finalização, risco de bridge e capital preso.

---

## 11. Bounded context recomendado

Não misturar arbitragem cripto com entidades de mercados preditivos.

```text
backend/app/crypto_arbitrage/
├── domain/
│   ├── enums.py
│   ├── models.py
│   ├── money.py
│   ├── symbols.py
│   ├── fees.py
│   └── errors.py
├── connectors/
│   ├── base.py
│   ├── registry.py
│   ├── binance/
│   ├── okx/
│   ├── bybit/
│   ├── kraken/
│   ├── coinbase/
│   ├── kucoin/
│   ├── jupiter/
│   ├── oneinch/
│   ├── uniswap/
│   ├── curve/
│   ├── raydium/
│   └── pancakeswap/
├── market_data/
│   ├── local_book.py
│   ├── stream_manager.py
│   ├── freshness.py
│   ├── clock_sync.py
│   └── latency.py
├── opportunities/
│   ├── scanner.py
│   ├── cex_cex.py
│   ├── triangular.py
│   ├── cex_dex.py
│   ├── dex_dex.py
│   └── profitability.py
├── execution/
│   ├── policy.py
│   ├── planner.py
│   ├── coordinator.py
│   ├── oms.py
│   ├── reconciliation.py
│   ├── compensation.py
│   └── idempotency.py
├── risk/
│   ├── engine.py
│   ├── limits.py
│   ├── circuit_breaker.py
│   ├── inventory.py
│   ├── exposure.py
│   └── kill_switch.py
├── dex/
│   ├── quote_validation.py
│   ├── gas.py
│   ├── simulation.py
│   ├── mev.py
│   └── signing_gateway.py
├── persistence/
│   ├── models.py
│   ├── repositories.py
│   └── database.py
├── services/
│   ├── scanner_service.py
│   ├── collector.py
│   ├── account_reader.py
│   └── health.py
└── api/
    ├── market_data.py
    ├── opportunities.py
    ├── accounts.py
    ├── risk.py
    └── execution.py
```

---

## 12. Interfaces mínimas

### CEX pública

```python
from typing import AsyncIterator, Protocol

class PublicCexConnector(Protocol):
    venue_id: str

    async def list_instruments(self) -> list["Instrument"]: ...
    async def get_order_book(self, instrument_id: str, depth: int) -> "OrderBookSnapshot": ...
    async def stream_order_books(self, instruments: list[str]) -> AsyncIterator["OrderBookEvent"]: ...
    async def get_server_time(self) -> int: ...
    async def health(self) -> "ConnectorHealth": ...
```

### Conta privada read-only

```python
class PrivateAccountReader(Protocol):
    async def balances(self) -> list["Balance"]: ...
    async def open_orders(self) -> list["OrderRecord"]: ...
    async def fills(self) -> list["Fill"]: ...
    async def fee_schedule(self) -> list["FeeRate"]: ...
    async def permissions(self) -> "ApiPermissions": ...
```

### Execução futura

Não registrar adapter real antes das fases read-only/testnet.

```python
class TradingAdapter(Protocol):
    async def validate_order(self, intent: "OrderIntent") -> "OrderValidation": ...
    async def submit_order(
        self,
        intent: "OrderIntent",
        authorization: "ExecutionAuthorization",
    ) -> "OrderRecord": ...
    async def cancel_order(self, order_id: str) -> "OrderRecord": ...
```

`submit_order` deve exigir autorização explícita, auditável e limitada.

### DEX quote

```python
class DexQuoteConnector(Protocol):
    chain_id: str
    venue_id: str

    async def quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        slippage_bps: int,
    ) -> "DexQuote": ...

    async def simulate(self, quote: "DexQuote") -> "TransactionSimulation": ...
```

---

## 13. Modelos mínimos

Usar `Decimal`, nunca `float`, para valores financeiros.

### Instrument

```text
venue_id, instrument_id, base_asset, quote_asset, market_type,
chain_id opcional, token addresses opcionais, price_tick,
quantity_step, min_quantity, min_notional, status
```

### OrderBookSnapshot

```text
venue_id, instrument_id, bids, asks, sequence,
exchange_timestamp, received_timestamp, normalized_timestamp,
is_snapshot, is_stale, checksum opcional
```

### FeeRate

```text
venue_id, instrument/product_type, maker_rate, taker_rate,
source, effective_at, expires_at
```

### Opportunity

```text
opportunity_id, strategy_type, buy_venue, sell_venue,
instrument, requested_quantity, executable_quantity,
buy_vwap, sell_vwap, gross_edge, gross_profit, total_fees,
slippage_cost, gas_cost, network_cost, hedge_cost,
safety_buffer, expected_net_profit, expected_roi,
data_age_ms, latency_ms, expires_at, risk_status
```

### ExecutionPlan

```text
plan_id, opportunity_id, legs, maximum_total_notional,
minimum_expected_profit, maximum_slippage_bps, deadline,
execution_mode, risk_decision_id, authorization_id opcional
```

### OrderIntent

```text
client_order_id, venue_id, instrument_id, side, order_type,
quantity, limit_price, time_in_force, reduce_only,
deadline, idempotency_key
```

### Fill

```text
venue_id, order_id, trade_id, price, quantity,
fee, fee_asset, timestamp
```

### RiskDecision

```text
approved, reasons, limits_snapshot, market_data_age,
inventory_check, balance_check, fee_check, latency_check,
circuit_breaker_state
```

---

## 14. Dados em tempo real

REST periódico não serve como hot path de arbitragem.

Cada conector CEX deve:

1. obter snapshot inicial;
2. abrir WebSocket;
3. aplicar deltas em ordem;
4. validar sequence/checksum;
5. detectar gaps;
6. refazer snapshot;
7. medir timestamp da exchange e recebimento;
8. calcular idade do book;
9. marcar stale;
10. bloquear oportunidades stale;
11. reconectar com backoff/jitter;
12. respeitar rate limits;
13. expor métricas.

Métricas:

```text
market_data_messages_total
market_data_gap_total
market_data_reconnect_total
orderbook_age_ms
exchange_to_receive_latency_ms
local_processing_latency_ms
connector_error_total
connector_rate_limit_total
```

---

## 15. Lucratividade

Não comparar last price. Calcular VWAP pela profundidade.

```text
buy_vwap  = custo total / quantidade preenchida
sell_vwap = receita total / quantidade preenchida
```

Fórmula mínima:

```text
gross_profit = sell_proceeds - buy_cost

expected_net_profit =
    gross_profit
    - buy_trading_fee
    - sell_trading_fee
    - slippage_reserve
    - gas_cost
    - priority_fee
    - bridge_cost
    - withdrawal_cost
    - funding_cost
    - borrow_cost
    - hedge_cost
    - failure_risk_buffer
    - operational_safety_buffer
```

Uma oportunidade só pode ser executável quando:

- todas as taxas são conhecidas;
- books estão recentes;
- profundidade cobre a quantidade;
- saldos estão disponíveis/reservados;
- precisões/mínimos são respeitados;
- expected net profit e ROI superam limites;
- latência está aceitável;
- circuit breakers estão fechados;
- não depende de saque/transferência no hot path;
- há prazo curto e plano de compensação.

---

## 16. Inventário e capital

Arbitragem CEX-CEX deve usar capital pré-posicionado.

```text
CEX A: USDT para comprar BTC
CEX B: BTC para vender por USDT
```

Separar execução da oportunidade e rebalanceamento.

Acompanhar:

```text
available
reserved
pending_order
pending_withdrawal
pending_deposit
on_chain_pending
target_allocation
deviation
```

Nunca aguardar depósito/saque entre as duas pernas.

---

## 17. Execução de duas pernas

Não há atomicidade entre CEXs.

Políticas possíveis:

- simultânea;
- leg-first;
- maker-taker.

O `ExecutionCoordinator` futuro deve:

1. reservar saldo;
2. revalidar oportunidade;
3. gerar IDs idempotentes;
4. submeter conforme política;
5. acompanhar eventos privados;
6. reconciliar REST/WS;
7. detectar fill parcial;
8. cancelar restante;
9. executar hedge emergencial dentro do limite;
10. registrar resultado;
11. liberar reservas;
12. atualizar risco.

---

## 18. DEX/Web3

### Quote mínima

```text
chain_id, block_number/slot, token_in, token_out, amount_in,
expected_amount_out, minimum_amount_out, price_impact, route,
estimated_gas, priority_fee, quote_timestamp, expires_at,
spender, transaction_payload_hash
```

### Antes de assinar

Validar:

- chain;
- token addresses/decimals;
- allowance;
- estado atual;
- simulation;
- minimum amount out;
- gas/priority fee;
- nonce/blockhash;
- saldo;
- deadline;
- router/contrato allowlisted;
- ausência de chamadas inesperadas.

### SigningGateway

- signer isolado;
- nenhuma private key no frontend ou Git;
- preferir KMS/HSM/serviço externo;
- limites por chain/contrato/transação;
- kill switch próprio;
- logs sem segredo.

### MEV

Considerar sandwich, frontrun, backrun, private relay, Jito bundles, prioridade e falha de inclusão.

### Solana

Slot freshness, blockhash, compute units, priority fee, account locks, simulation, ALT, confirmação e retry idempotente.

### EVM

Chain ID, nonce, EIP-1559, allowance, Permit2 quando aplicável, deadline, minOut, reorg, receipt e gas.

---

## 19. Cross-chain

LayerZero é mensageria omnichain; Stargate transporta liquidez cross-chain. Não tratar como operação instantânea/atômica.

Modelo futuro:

```text
transfer_id, source_chain, destination_chain, source_tx,
destination_tx, asset, amount_sent, amount_received,
quoted_fee, actual_fee, timestamps, status, recovery_action
```

Estados:

```text
QUOTED
SUBMITTED
SOURCE_CONFIRMED
IN_TRANSIT
DELIVERED
FAILED
MANUAL_REVIEW
```

---

## 20. Persistência futura

Entidades sugeridas:

```text
crypto_venues
crypto_instruments
crypto_fee_schedules
crypto_market_data_health
crypto_opportunities
crypto_opportunity_legs
crypto_execution_plans
crypto_orders
crypto_fills
crypto_balances
crypto_inventory_reservations
crypto_risk_decisions
crypto_circuit_breakers
crypto_dex_quotes
crypto_transactions
crypto_cross_chain_transfers
crypto_reconciliation_events
crypto_audit_events
```

Não persistir todo delta bruto no banco transacional. Para alta frequência considerar futuramente ClickHouse, TimescaleDB, Parquet ou object storage.

---

## 21. Observabilidade

Dashboard futuro deve exibir:

- status por conector;
- WebSocket conectado;
- último evento;
- idade do book;
- latência;
- gaps/reconnects;
- rate limits;
- instrumentos;
- oportunidades brutas e líquidas;
- motivos de rejeição;
- inventário/exposição;
- circuit breakers;
- ordens/fills;
- reconciliação;
- PnL esperado versus realizado;
- gas/slippage;
- kill switch.

Alertas:

```text
book stale
sequence gap
API privada desconectada
saldo insuficiente
fill unilateral
divergência de ordem
perda acima do limite
latência alta
gas anormal
nonce preso
transação revertida
bridge atrasada
erro de autenticação
rate limit
mudança de permissão da API
```

---

## 22. Segurança de credenciais

### CEX

Separar chaves:

```text
market-data-public: sem segredo
account-read-only: somente leitura
trading-testnet: trade apenas em testnet
trading-live: trade sem saque
```

Aplicar:

- IP whitelist;
- saque desativado;
- subconta dedicada;
- capital limitado;
- rotação;
- permissões mínimas;
- monitoramento/revogação.

### Web3

- carteira dedicada por chain;
- capital limitado;
- contratos allowlisted;
- approvals limitadas;
- signer isolado;
- saldo de gas limitado;
- seed phrase nunca em `.env`;
- secrets fora do Git.

---

## 23. Roadmap recomendado

### Fase 17 — CONCLUÍDA

Merge `823d84f`, tag `phase-17-background-radar-collector`, implantada e validada em produção em 01/08/2026. Todos os critérios da seção 25 aprovados. Resultado registrado na seção 5.

Ficou de fora, por ser independente desta fase:

- ligar a exigência de autenticação em produção (seção 4) — **feito em 02/08/2026**;
- `/docs` e `/openapi.json` respondem publicamente — **ainda aberto**; não é fechado pelas flags de autenticação e continua expondo a superfície completa da API.

Os dois defeitos de experiência de login registrados na seção 4 também seguem em aberto e não têm fase atribuída.

### Fase 18 — domínio cripto read-only — CONCLUÍDA

Implementada em 02/08/2026. Detalhes na seção 5.

- bounded context;
- modelos `Decimal`;
- enums/interfaces/registry;
- mocks;
- nenhum segredo;
- nenhum endpoint de ordem.

Aceitação: testes unitários e flags financeiras falsas. **Aprovada** com 752 testes no total.

### Fase 19 — Binance, OKX e Bybit públicos

Dividida em três incrementos, porque a fase inteira num único PR não é revisável e contraria a regra 6 da seção 1.

**19A — fundação de market data. CONCLUÍDA em 02/08/2026.**

Lógica pura em `backend/app/crypto_arbitrage/market_data/`, sem rede: `local_book.py`, `freshness.py` e `latency.py`. Detalhes na seção 5.

**19B — adaptadores das três venues. CONCLUÍDA em 02/08/2026.**

Tradução dos formatos públicos para o domínio, em `backend/app/crypto_arbitrage/connectors/`, sem rede. Formatos revalidados na documentação oficial conforme a seção 29. Detalhes na seção 5, incluindo dois achados que alteraram o planejamento: a Bybit não documenta continuidade de sequência, e o checksum da OKX foi depreciado em 23/06/2026.

**19C1 — orquestração de stream. CONCLUÍDA em 02/08/2026.**

Contratos de transporte, backoff com jitter, rate limit, métricas e o `BookStreamManager` que junta tudo. Ainda sem rede. Detalhes na seção 5.

**19C2 — transporte concreto.** Cliente REST com `httpx` e WebSocket com `websockets`, ambos já no `requirements.txt`: a fase não acrescenta dependência. Inclui ping/pong, laço de reconexão e o fluxo documentado de sincronização inicial de cada venue. É o incremento que finalmente toca a rede, e onde entram testes de integração `opt-in`, marcados para não rodar por padrão — a seção 28 exige que os testes padrão não dependam de internet.

Aceitação da fase completa: três books normalizados, stale bloqueado e testes por fixtures. Os três critérios já estão satisfeitos; o 19C2 acrescenta o transporte real.

### Fase 20 — scanner CEX-CEX Paper — CONCLUÍDA

Dividida em quatro incrementos, todos implementados. Detalhes na seção 5.

- **20A** motor de lucratividade e scanner espacial — VWAP, taxas, slippage/buffer, ranking;
- **20B** coletor com job de scheduler, por REST e não WebSocket;
- **20C** API autenticada;
- **20D** painel no dashboard.

Nenhuma ordem real. As Fases 20A a 20C estão em produção desde 03/08/2026, com o coletor desligado; a 20D segue em branch, sem merge.

### Fase 21 — replay/backtesting

- gravação amostrada;
- replay;
- latência/fills parciais;
- expected versus realized;
- relatórios reproduzíveis.

### Fase 22 — Kraken, Coinbase e KuCoin públicos

Mesmas exigências da Fase 19.

### Fase 23 — Jupiter e 1inch read-only

- quotes/rotas;
- impact/gas/priority fee;
- expiração;
- simulation;
- nenhuma assinatura/transmissão.

### Fase 24 — scanner CEX-DEX Paper

- token normalization;
- inventário por venue/chain;
- gas/slippage/MEV buffer;
- oportunidade líquida Paper.

### Fase 25 — contas privadas read-only

- balances;
- fees;
- open orders;
- fills;
- permissions;
- subaccounts;
- chaves sem trade;
- logs sanitizados.

### Fase 26 — execução testnet

- OMS;
- idempotência;
- reservas;
- reconciliação;
- fills parciais;
- circuit breakers;
- kill switch;
- nenhum endpoint mainnet registrado.

### Fase 27 — canary live controlado

Somente após autorização explícita e checklist completo.

Pré-condições:

- auditoria;
- subconta dedicada;
- saque desativado;
- limites diários/ordem/ativo;
- kill switch;
- monitoramento;
- reconciliação;
- alertas;
- capital mínimo;
- rollback;
- aprovação manual inicial.

### Fase 28 — DEX devnet/testnet/fork

- Jupiter/Raydium Devnet quando disponível;
- EVM fork/testnet;
- signer isolado;
- simulation/allowlist;
- faucet assets.

### Fase 29 — DEX live canary

Somente após auditoria de smart contracts, signing e MEV.

### Fase 30 — cross-chain/rebalanceamento

- Stargate/LayerZero;
- estados persistentes;
- recuperação/manual review;
- fora do hot path.

---

## 24. Primeira ação do Claude Code

Executar somente:

```powershell
Set-Location C:\predarb-framework

git status --short --branch
git log --oneline -6
git rev-list --left-right --count origin/main...HEAD
git diff --stat
```

Depois:

1. comparar o estado real com a seção 3 e apontar divergências antes de qualquer outra coisa;
2. confirmar ausência de segredo;
3. confirmar flags financeiras desativadas;
4. não commitar, empurrar, merjar ou taguear sem autorização;
5. não iniciar a Fase 18 até o usuário autorizar.

Se o working tree estiver limpo, não invente diffs a revisar: relate o estado e pergunte qual o próximo passo.

---

## 25. Validação de produção da Fase 17

### Status

```text
GET /real-markets/radar/collector/status
```

Esperado:

```text
enabled=true
cycles >= 1
successes >= 1
failures=0
read_only=true
execution_authorized=false
financial_execution=false
order_submission_available=false
```

### Snapshot

```text
GET /real-markets/radar/snapshot
```

Esperado:

```text
status=READY
monitoring.snapshot_available=true
monitoring.served_from_snapshot=true
read_only=true
financial_execution=false
```

Duas chamadas ao snapshot não devem criar coleta.

### Persistência

Depois de dois ciclos:

- histórico `source=persistent`;
- pelo menos dois pontos em mercado estável;
- banco disponível;
- coleta inserida;
- sem erro.

### Reinício

Após restart:

- histórico continua;
- coletor volta;
- snapshot aquece no primeiro ciclo;
- banco principal permanece preservado.

---

## 26. Definition of Done para execução real

```text
[ ] WebSocket confiável
[ ] book local com sequence
[ ] stale detection
[ ] clock synchronization
[ ] taxas efetivas
[ ] precisões/mínimos
[ ] saldo/reserva
[ ] VWAP
[ ] slippage
[ ] latência
[ ] idempotência
[ ] OMS
[ ] eventos privados
[ ] reconciliação REST/WS
[ ] fills parciais
[ ] compensação
[ ] circuit breakers
[ ] kill switch
[ ] limites por ordem/dia/ativo/venue
[ ] logs/auditoria
[ ] alertas
[ ] testnet aprovada
[ ] soak/chaos tests
[ ] mínimo privilégio
[ ] saque desativado
[ ] subconta dedicada
[ ] autorização explícita
[ ] canary limitado
[ ] rollback operacional
```

---

## 27. Não objetivos imediatos

Não implementar agora:

- HFT em microssegundos/co-location;
- market making institucional;
- flash loans mainnet;
- contrato sem auditoria;
- bridge dentro da perna crítica;
- saque automático;
- seed phrase no sistema;
- IA autorizando ordem;
- alta alavancagem;
- múltiplos workers sem coordenação;
- live simultâneo em todas as venues.

---

## 28. Decisões técnicas

### Python/FastAPI

Manter no backend principal.

### Decimal

```python
from decimal import Decimal
```

Nunca usar `float` para preço, quantidade, taxa, PnL ou saldo.

### Concorrência

- async para rede;
- locks compatíveis;
- não compartilhar `asyncio.Lock` entre loops;
- single-flight protegido;
- filas bounded/backpressure;
- timeout/cancelamento seguro.

### WebSocket

Exigir reconexão, ping/pong, timeout, TLS, observabilidade e rate limiting.

Não adotar CCXT como abstração cega do hot path. Pode servir em protótipos, mas conectores críticos devem preservar sequence, canais privados e regras específicas.

### Testes

```text
unit
contract
fixture/replay
integration opt-in
testnet
soak
production read-only smoke
```

Testes padrão não dependem da internet.

---

## 29. Referências oficiais

Revalidar endpoints, domínios, rate limits, formatos e políticas antes de cada implementação.

```text
Binance
https://developers.binance.com/en/docs/introduction
https://developers.binance.com/en/docs/products/spot/rest-api

OKX
https://www.okx.com/docs-v5/

Bybit
https://bybit-exchange.github.io/docs/v5/intro
https://bybit-exchange.github.io/docs/v5/ws/connect
https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook

Kraken
https://docs.kraken.com/

Coinbase Advanced Trade
https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/introduction
https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-overview
https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-channels

KuCoin
https://www.kucoin.com/docs-new

1inch
https://portal.1inch.dev/

Jupiter
https://dev.jup.ag/

Uniswap
https://docs.uniswap.org/

Curve
https://docs.curve.finance/

Raydium
https://docs.raydium.io/
https://docs.raydium.io/sdk-api

PancakeSwap
https://developer.pancakeswap.finance/

LayerZero
https://docs.layerzero.network/

Stargate
https://docs.stargate.finance/
```

---

## 30. Prompt inicial para o Claude Code

```text
Leia integralmente o arquivo CLAUDE.md na raiz do projeto antes de agir.

Estamos em C:\predarb-framework, branch
feature/phase-20d-crypto-dashboard.

A Fase 20 está concluída em todos os quatro incrementos, com 996 testes
aprovados. As Fases 17 a 20C estão em produção; a 20D está commitada na
branch, sem merge e sem deploy.

ATENÇÃO: o Render está com auto-deploy on commit no branch main. Um push
para main é um deploy de produção. Não faça commit, push, merge, tag,
deploy, stash, reset ou descarte sem minha autorização.

Primeiro:
1. execute git status --short --branch e git log --oneline -6;
2. compare o estado real com a seção 3 e aponte divergências;
3. confirme que as proteções financeiras continuam desativadas;
4. informe qualquer risco ou inconsistência real.

Não altere arquivos ainda.

Depois decidiremos entre merjar a 20D, ligar o scanner cripto em produção
com CRYPTO_SCANNER_ENABLED, ou seguir para a Fase 21 (replay/backtesting).
Nenhuma execução real deverá ser habilitada sem autorização explícita e sem
cumprir o checklist definido no CLAUDE.md.

Seguem em aberto, sem fase atribuída: os dois defeitos de experiência de
login registrados na seção 4, a exposição pública de /docs e /openapi.json,
e a decisão sobre trocar MONOTONIC por STRICT_INCREMENT na Bybit.
```

---

## 31. Conclusão

O PredArb já possui uma base sólida de modularidade, scheduler, persistência, autenticação, observabilidade, simulação, dados reais read-only, dashboard e guardrails.

A expansão cripto deve aproveitar essa base, mas permanecer em domínio separado. Nunca inverter a sequência de segurança:

```text
read-only -> Paper -> replay -> testnet -> autorização -> canary -> expansão
```
