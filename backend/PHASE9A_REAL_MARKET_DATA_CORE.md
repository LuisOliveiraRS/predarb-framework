# PredArb — Fase 9A: Núcleo Consolidado de Dados de Mercado

A Fase 9A encerra temporariamente a trilha de certificações e inicia a
trilha funcional para integração com mercados reais.

Esta fase ainda não se conecta a corretoras externas. Ela cria o núcleo
padronizado que os conectores reais usarão a partir da Fase 9B.

## Objetivos

- centralizar o acesso a dados de mercado;
- definir um contrato único para conectores;
- permitir somente conectores read-only;
- normalizar mercados, outcomes, quotes e snapshots;
- manter cache com TTL;
- permitir atualização manual e confirmada;
- preparar a arquitetura para conectores externos;
- impedir qualquer envio de ordem.

## Componentes adicionados

```text
app/real_markets/
├── __init__.py
├── models.py
├── connectors.py
├── registry.py
└── service.py
```

Também são adicionados:

```text
app/api/routers/real_market_data.py
tests/test_real_market_data_core.py
```

## Modelos normalizados

### NormalizedMarket

Representa um mercado de previsão independentemente da plataforma.

Campos principais:

- `connector_id`;
- `market_id`;
- `title`;
- `status`;
- `outcomes`;
- `close_time`;
- `currency`;
- `category`;
- `source_url`;
- `metadata`.

### MarketQuote

Representa a cotação de um outcome:

- `bid`;
- `ask`;
- `last`;
- `bid_size`;
- `ask_size`;
- `spread`;
- `midpoint`.

Os preços são validados no intervalo entre `0` e `1`.

### MarketSnapshot

Reúne:

- mercado normalizado;
- quotes atuais;
- horário da captura;
- latência da fonte;
- referência bruta opcional;
- metadados.

## Contrato de conectores

Todo conector precisa implementar:

```python
async def health()
async def list_markets(limit=100)
async def get_snapshot(market_id)
```

O registro rejeita conectores que não tenham:

```python
read_only = True
```

## Conector de validação

A Fase 9A registra somente:

```text
mock-real-market
```

Esse conector fornece dois mercados fictícios para validar a arquitetura.

Nenhuma API externa é acessada nesta fase.

## Rotas

```text
GET  /real-markets/health
GET  /real-markets/connectors
GET  /real-markets/markets
GET  /real-markets/markets/{connector_id}/{market_id}
GET  /real-markets/snapshots/latest
GET  /real-markets/dashboard
GET  /real-markets/architecture

POST /real-markets/refresh
```

## Confirmação da atualização

```text
REFRESH-REAL-MARKET-DATA
```

A atualização altera apenas o cache de dados de mercado.

## Dashboard

```text
http://127.0.0.1:8000/real-markets/dashboard
```

O painel mostra:

- saúde do núcleo;
- conectores registrados;
- capacidades de cada conector;
- mercados normalizados;
- snapshots em cache;
- idade do cache;
- falhas de atualização;
- botão de atualização manual.

## Segurança

```json
{
  "market_data_only": true,
  "read_only": true,
  "paper_execution_authorized": false,
  "live_authorization": false,
  "execution_authorized": false,
  "live_execution": false,
  "financial_execution": false,
  "next_step_authorized": false
}
```

Nenhum componente desta fase:

- assina transações;
- lê chaves privadas;
- envia ordens;
- cancela ordens;
- movimenta saldo;
- inicia runtime em background;
- autoriza operação real.

## Instalação

Execute dentro de:

```text
C:\predarb-framework\backend
```

Comando:

```powershell
python ".\scripts\real_tests\install_phase9a_real_market_data_core.py"
```

## Testes

```powershell
python -m pytest -q tests\test_real_market_data_core.py
python -m pytest -q
```

A Fase 9A adiciona 12 testes.

Considerando os 377 testes esperados até a Fase 8AV, a expectativa passa
a ser de 389 testes aprovados. O resultado do terminal é a confirmação
efetiva.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase9a_real_market_data_core_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

O checker executa oito verificações e atualiza apenas o cache em memória.

## Próxima etapa funcional

A Fase 9B deverá adicionar o primeiro conector externo somente leitura,
mantendo o contrato criado nesta fase.

Escopo previsto:

- conexão HTTP com uma plataforma real;
- timeout e retentativas;
- normalização dos mercados;
- normalização de bid, ask e liquidez;
- tratamento de rate limit;
- nenhum endpoint de trading;
- nenhuma credencial de execução.
