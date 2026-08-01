# CLAUDE.md — Contexto Mestre do PredArb Framework

> Coloque este arquivo na raiz de `C:\predarb-framework` para servir como contexto principal do Claude Code no VSCode.
>
> Data do contexto: 31/07/2026.
>
> Estado crítico: a Fase 17 está implementada, commitada e enviada ao `origin` no branch de feature, mas ainda **não** foi merjada nem implantada em produção.

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
feature/phase-17-background-radar-collector
```

### Base conhecida

```text
574d383
```

Esse commit corresponde ao merge da correção de isolamento do banco de observações da Fase 16.

### Commits da Fase 17

O trabalho da Fase 17 está protegido por commit. Não há mais alterações pendentes no working tree.

```text
78d0fef feat: collect real opportunity radar in background
        12 arquivos, +1537/-94
        coletor, scheduler task, application, settings,
        dashboard e testes de snapshot/freshness

a556744 feat: throttle external radar force refresh and require auth
        6 arquivos, +511/-2
        cooldown de force_refresh e autenticação no /opportunities
```

Branch sincronizado com `origin/feature/phase-17-background-radar-collector` até o commit `78d0fef`. O commit de guardrails ainda **não** foi enviado — push, PR, merge, tag e deploy seguem exigindo autorização explícita.

O arquivo `CLAUDE_CODE_PROMPT_INICIAL.txt` permanece fora do versionamento: duplica a seção 30 deste documento e tende a divergir dela.

### Última validação completa

```text
688 passed, 2 warnings in 114.38s
git diff --check: aprovado
auditoria de flags financeiras: 12/12 False em 511 ocorrências
varredura de segredos no diff: nenhum indício
```

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

Consequências:

- o processo pode dormir ou reiniciar;
- memória e cache são locais ao processo;
- persistência Supabase deve sobreviver aos reinícios;
- não assumir coordenação distribuída entre múltiplos workers.

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

### 17 — coletor automático, commitada e pendente de deploy

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

### Fase 17 — concluir e publicar

Estado: código commitado no branch de feature. Falta publicar.

Concluído:

1. ~~revisar diff~~ — feito;
2. ~~commit autorizado~~ — `78d0fef` e o commit de guardrails;
3. ~~confirmar flags falsas~~ — 12/12 `False`.

Pendente:

4. push do commit de guardrails;
5. PR, merge e tag;
6. configurar env no Render, incluindo `REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS`;
7. deploy;
8. validar status/snapshot;
9. validar persistência e reinício;
10. revalidar `/opportunities` autenticado em produção, já que deixou de ser público.

### Fase 18 — domínio cripto read-only

- bounded context;
- modelos `Decimal`;
- enums/interfaces/registry;
- mocks;
- nenhum segredo;
- nenhum endpoint de ordem.

Aceitação: testes unitários e flags financeiras falsas.

### Fase 19 — Binance, OKX e Bybit públicos

- instruments;
- REST snapshot;
- WebSocket;
- book local;
- sequence/gap/resync;
- freshness/reconnect/rate limit/health.

Aceitação: três books normalizados, stale bloqueado e testes por fixtures.

### Fase 20 — scanner CEX-CEX Paper

- VWAP;
- taxas;
- slippage/buffer;
- ranking;
- dashboard;
- nenhuma ordem real.

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
git rev-list --left-right --count `
  origin/feature/phase-17-background-radar-collector...HEAD
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
feature/phase-17-background-radar-collector.

A Fase 17 está implementada, commitada e validada com 688 testes aprovados,
mas ainda não foi merjada nem implantada. Não faça commit, push, merge, tag,
deploy, stash, reset ou descarte sem minha autorização.

Primeiro:
1. execute git status --short --branch e git log --oneline -6;
2. compare o estado real com a seção 3 e aponte divergências;
3. faça um resumo técnico do que ainda falta na Fase 17;
4. confirme que as proteções financeiras continuam desativadas;
5. informe qualquer risco ou inconsistência real.

Não altere arquivos ainda.

Depois seguiremos com a conclusão da Fase 17 e a expansão para o novo
bounded context de arbitragem de criptomoedas CEX/DEX/Web3, começando
somente por dados públicos e simulação. Nenhuma execução real deverá ser
habilitada sem autorização explícita e sem cumprir o checklist definido
no CLAUDE.md.
```

---

## 31. Conclusão

O PredArb já possui uma base sólida de modularidade, scheduler, persistência, autenticação, observabilidade, simulação, dados reais read-only, dashboard e guardrails.

A expansão cripto deve aproveitar essa base, mas permanecer em domínio separado. Nunca inverter a sequência de segurança:

```text
read-only -> Paper -> replay -> testnet -> autorização -> canary -> expansão
```
