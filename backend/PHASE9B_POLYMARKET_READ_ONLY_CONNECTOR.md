# PredArb — Fase 9B: Conector Polymarket Somente Leitura

A Fase 9B adiciona o primeiro conector externo do núcleo funcional criado
na Fase 9A.

O conector utiliza somente endpoints públicos da Polymarket:

- Gamma API para descobrir eventos e mercados;
- CLOB público para consultar orderbooks;
- nenhuma autenticação;
- nenhuma carteira;
- nenhuma chave privada;
- nenhum endpoint de trading.

## Base técnica

Implementação baseada na documentação pública oficial da Polymarket:

```text
https://docs.polymarket.com/api-reference/introduction
https://docs.polymarket.com/market-data/fetching-markets
https://docs.polymarket.com/api-reference/market-data/get-order-book
https://docs.polymarket.com/api-reference/rate-limits
https://docs.polymarket.com/v2-migration
```

## Fluxo de dados

```text
Gamma API
   │
   ├── eventos ativos
   ├── mercados
   ├── outcomes
   ├── token IDs
   └── metadados
   │
   ▼
PolymarketReadOnlyConnector
   │
   ├── normalização
   ├── validação
   └── associação outcome/token
   │
   ▼
CLOB público /book
   │
   ├── melhor bid
   ├── melhor ask
   ├── tamanho
   └── último preço negociado
   │
   ▼
MarketSnapshot
   │
   ▼
RealMarketDataService
```

## Arquivos adicionados

```text
app/real_markets/polymarket.py
app/api/routers/polymarket_read_only.py
tests/test_polymarket_read_only_connector.py
```

O instalador também registra o conector no serviço da Fase 9A e inclui o
novo router no `application.py`.

## Conector

```text
connector_id: polymarket
name: Polymarket Public Market Data
read_only: true
authentication_required: false
trading_endpoints_enabled: false
```

## Recursos

- consulta de eventos ativos;
- normalização de mercados;
- leitura de outcomes e token IDs;
- consulta concorrente dos orderbooks;
- melhor bid e melhor ask;
- tamanho disponível no primeiro nível;
- último preço negociado;
- spread e midpoint;
- timeout;
- retentativas para `429` e falhas `5xx`;
- suporte ao header `Retry-After`;
- health check Gamma + CLOB;
- possibilidade de desativação por ambiente;
- integração automática ao dashboard da Fase 9A.

## Rotas específicas

```text
GET /real-markets/polymarket/configuration
GET /real-markets/polymarket/health
GET /real-markets/polymarket/markets
GET /real-markets/polymarket/markets/{market_id}/snapshot
GET /real-markets/polymarket/architecture
```

Todas são GET e somente leitura.

As rotas consolidadas da Fase 9A também passam a aceitar:

```text
GET  /real-markets/markets?connector_id=polymarket
POST /real-markets/refresh?connector_id=polymarket
```

O POST de refresh altera somente o cache em memória.

## Variáveis opcionais

```env
POLYMARKET_READ_ONLY_ENABLED=true
POLYMARKET_GAMMA_BASE_URL=https://gamma-api.polymarket.com
POLYMARKET_CLOB_BASE_URL=https://clob.polymarket.com
POLYMARKET_TIMEOUT_SECONDS=12
POLYMARKET_MAX_RETRIES=2
POLYMARKET_RETRY_BASE_SECONDS=0.25
POLYMARKET_DEFAULT_MARKET_LIMIT=50
POLYMARKET_ALLOW_INSECURE_HTTP=false
```

Não é necessário inserir credenciais.

## Segurança

```json
{
  "market_data_only": true,
  "read_only": true,
  "authentication_required": false,
  "trading_endpoints_enabled": false,
  "paper_execution_authorized": false,
  "live_authorization": false,
  "execution_authorized": false,
  "live_execution": false,
  "financial_execution": false,
  "next_step_authorized": false
}
```

O conector não contém métodos para:

- criar ordens;
- cancelar ordens;
- assinar mensagens;
- acessar carteira;
- ler saldo;
- movimentar fundos;
- usar chave privada;
- criar credenciais;
- iniciar runtime automático.

## Instalação

Execute dentro de:

```text
C:\predarb-framework\backend
```

Comando:

```powershell
python ".\scripts\real_tests\install_phase9b_polymarket_read_only_connector.py"
```

A Fase 9A precisa estar instalada.

## Testes

```powershell
python -m pytest -q tests\test_polymarket_read_only_connector.py
python -m pytest -q
```

A Fase 9B adiciona 10 testes.

Considerando os 389 testes esperados até a Fase 9A, a expectativa passa
a ser de 399 testes aprovados. O terminal do projeto é a confirmação real.

Os testes usam `httpx.MockTransport`, portanto não dependem da internet.

## Validação HTTP real

Com o servidor iniciado:

```powershell
python ".\scripts\real_tests\phase9b_polymarket_read_only_connector_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

O checker realiza oito verificações e consulta a API pública real.

A validação HTTP depende de:

- acesso à internet;
- resolução DNS;
- disponibilidade das APIs públicas;
- ausência de bloqueio de rede local;
- compatibilidade regional do acesso.

## Dashboard consolidado

```text
http://127.0.0.1:8000/real-markets/dashboard
```

O conector `polymarket` aparecerá ao lado de `mock-real-market`.

## Próxima fase funcional

A Fase 9C deverá tratar correspondência e identidade de mercados:

- fingerprint normalizado;
- datas e condições de resolução;
- similaridade textual;
- correspondência manual confirmada;
- rejeição de falsos pares;
- grupos equivalentes entre plataformas.

Nenhuma execução será introduzida na Fase 9C.
