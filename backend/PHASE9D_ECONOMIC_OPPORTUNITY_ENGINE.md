# PredArb — Fase 9D: Motor Econômico de Oportunidades

A Fase 9D transforma correspondências manuais confirmadas da Fase 9C em
avaliações econômicas simuladas.

Ela calcula custo, liquidez, taxas, slippage, payout, lucro e edge, sem
enviar ordens e sem movimentar saldo.

## Escopo funcional

A versão inicial suporta mercados binários:

```text
YES / NO
SIM / NÃO
```

Para cada par confirmado, são avaliadas duas direções:

```text
YES no mercado esquerdo + NO no mercado direito
NO no mercado esquerdo  + YES no mercado direito
```

## Cálculo

Para cada direção:

```text
quantidade simulada =
    menor ask_size entre as duas pernas
    limitada pela quantidade máxima configurada

custo bruto =
    ask esquerdo × quantidade
    + ask direito × quantidade

taxas estimadas =
    custo de cada perna × taxa configurada do conector

slippage estimado =
    custo de cada perna × slippage configurado em bps

custo total =
    custo bruto + taxas + slippage

payout simulado =
    quantidade

lucro líquido =
    payout simulado - custo total

edge líquido =
    lucro líquido / payout simulado
```

## Guardas econômicas

A oportunidade é rejeitada quando:

- o snapshot está antigo;
- o horário de captura é inválido;
- os grupos de moeda são incompatíveis;
- não existe ask;
- não existe ask_size;
- a liquidez é zero;
- o mercado não possui estrutura binária canônica;
- o par usa o mesmo conector.

Uma direção é `PROFITABLE` somente quando atende simultaneamente:

- edge líquido mínimo;
- lucro líquido mínimo.

## Estados

```text
PROFITABLE
NOT_PROFITABLE
REJECTED
ERROR
NO_CONFIRMED_MATCHES
EVALUATED
```

## Arquivos adicionados

```text
app/real_markets/economics.py
app/api/routers/economic_opportunities.py
tests/test_economic_opportunity_engine.py
```

## Rotas

```text
GET /real-markets/economics/health
GET /real-markets/economics/configuration
GET /real-markets/economics/opportunities
GET /real-markets/economics/matches/{match_id}
GET /real-markets/economics/preview
GET /real-markets/economics/dashboard
GET /real-markets/economics/architecture
```

Todas as rotas são de análise. Não existe rota de criação, cancelamento ou
envio de ordens.

## Preview não confirmado

A rota `/preview` permite avaliar economicamente dois mercados sem
persisti-los como correspondência.

O resultado inclui:

```json
{
  "source": "UNCONFIRMED_PREVIEW",
  "manual_match_confirmed": false,
  "execution_authorized": false
}
```

Esse preview não substitui a confirmação manual da Fase 9C.

## Dashboard

```text
http://127.0.0.1:8000/real-markets/economics/dashboard
```

O painel mostra:

- pares confirmados;
- oportunidades lucrativas;
- pares não lucrativos;
- pares rejeitados;
- quantidade simulada;
- custo bruto;
- taxas;
- slippage;
- lucro líquido;
- edge líquido;
- dados faltantes ou antigos.

## Configurações opcionais

```env
REAL_MARKET_ECONOMIC_MAX_SNAPSHOT_AGE_SECONDS=90
REAL_MARKET_ECONOMIC_MAX_SIMULATED_QUANTITY=1000
REAL_MARKET_ECONOMIC_MIN_NET_EDGE=0.0025
REAL_MARKET_ECONOMIC_MIN_NET_PROFIT=0.01
```

Taxas estimadas por conector:

```env
REAL_MARKET_ECONOMIC_FEE_RATES_JSON={"default":0.0,"mock-real-market":0.0,"polymarket":0.0}
```

Slippage em basis points:

```env
REAL_MARKET_ECONOMIC_SLIPPAGE_BPS_JSON={"default":10,"mock-real-market":0,"polymarket":10}
```

Grupos de moeda usados somente para compatibilidade da simulação:

```env
REAL_MARKET_ECONOMIC_CURRENCY_GROUPS_JSON={"USD":"USD_STABLE","USDC":"USD_STABLE","USDT":"USD_STABLE","PUSD":"USD_STABLE"}
```

Esses grupos não executam conversão cambial e não afirmam equivalência de
liquidação. Eles apenas impedem a soma direta de unidades fora do grupo
configurado.

## Segurança

```json
{
  "economic_analysis_only": true,
  "shadow_only": true,
  "market_data_only": true,
  "read_only_market_access": true,
  "order_submission_available": false,
  "automatic_execution_authorized": false,
  "paper_execution_authorized": false,
  "live_authorization": false,
  "execution_authorized": false,
  "live_execution": false,
  "financial_execution": false,
  "next_step_authorized": false
}
```

## Instalação

Execute dentro de:

```text
C:\predarb-framework\backend
```

Comando:

```powershell
python ".\scripts\real_tests\install_phase9d_economic_opportunity_engine.py"
```

As Fases 9A e 9C precisam estar instaladas.

## Testes

```powershell
python -m pytest -q tests\test_economic_opportunity_engine.py
python -m pytest -q
```

A Fase 9D adiciona 12 testes.

Considerando os 412 testes esperados até a Fase 9C, a expectativa passa
a ser de 424 testes aprovados. O terminal do projeto é a confirmação real.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase9d_economic_opportunity_engine_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

O checker:

- valida a configuração;
- localiza um mercado mock;
- localiza um mercado Polymarket;
- executa um preview econômico não confirmado;
- consulta oportunidades de pares confirmados;
- valida dashboard e arquitetura.

Ele não cria correspondências e não envia ordens.

## Próxima fase funcional

A Fase 9E deverá implementar shadow execution:

- congelamento do snapshot usado na decisão;
- ordem simulada por perna;
- preenchimento simulado;
- execução parcial simulada;
- slippage observado;
- divergência entre preço esperado e preço posterior;
- resultado hipotético;
- diário de shadow trades.

Ainda sem credenciais de trading e sem conta real.
