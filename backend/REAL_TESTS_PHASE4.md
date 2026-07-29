# PredArb — Testes Reais, Fase 4

## Objetivo

Validar o Pipeline de **Paper Trading** com dados públicos reais da Hyperliquid, sem enviar ordens e sem alterar o estado operacional do OMS.

O teste usa:

- `HyperliquidConnector` somente leitura;
- `MockConnector` para validar o ambiente dual;
- um mercado de controle local, criado apenas no processo de teste a partir de uma pergunta real da Hyperliquid;
- `CrossPlatformComparator` oficial;
- Pipeline `analysis` oficial;
- Pipeline `paper` oficial;
- AI consultiva;
- `ExecutionEngine` e Pipeline live bloqueados.

O mercado de controle não é salvo no `MarketRepository` e não é publicado para a aplicação. Ele existe apenas para garantir uma rota reproduzível de Paper Trading quando não houver um mercado equivalente entre Mock e Hyperliquid.

## Segurança

A fase mantém:

```env
EXECUTION_WORKER_ENABLED=false
AI_ADVISORY_ONLY=true
AI_EXECUTION_AUTHORIZED=false
AI_AUTO_LOAD_MODEL=false
```

Nenhuma carteira, chave privada, API key ou endpoint de envio de ordens é utilizado.

## Arquivos

```text
scripts/real_tests/phase4_paper_trading.py
scripts/real_tests/phase4_server_paper_probe.py
REAL_TESTS_PHASE4.md
```

## 1. Teste integrado e determinístico

Na raiz do backend:

```powershell
cd C:\predarb-framework\backend
python ".\scripts\real_tests\phase4_paper_trading.py"
```

O teste valida:

1. lifecycle e guardas de segurança;
2. feed real da Hyperliquid;
3. rota cross-platform controlada;
4. Pipeline `analysis` e AI consultiva;
5. geração de duas intenções de ordem;
6. preenchimento simulado de YES e NO;
7. fees em Pipeline paper customizado;
8. replay com IDs exclusivos;
9. ausência de alteração no OMS, fills, trades, posições, PaperWallet e histórico legado;
10. Pipeline live desabilitado;
11. executor real não chamado.

Relatório:

```text
real_test_reports\phase4_paper_trading_report.json
```

## 2. Sonda contra o servidor Uvicorn

Mantenha o servidor aprovado da Fase 3 ativo. O health deve mostrar:

```text
mock_enabled=true
hyperliquid_enabled=true
scheduler.running=true
execution_worker=false
ai.execution_authorized=false
```

Em outro terminal:

```powershell
cd C:\predarb-framework\backend
python ".\scripts\real_tests\phase4_server_paper_probe.py" `
    --base-url "http://127.0.0.1:8000" `
    --cycles 3 `
    --interval-seconds 5
```

Essa sonda consome snapshots reais por HTTP e executa o Pipeline paper localmente. Ela não altera o processo do servidor.

Relatório:

```text
real_test_reports\phase4_server_paper_probe_report.json
```

## Resultado necessário para avançar

```text
phase4_paper_trading.py:       0 falhas
phase4_server_paper_probe.py:  0 falhas
ordens por ciclo:              2
fills paper por ciclo:         2
IDs de ordem reutilizados:     0
OMS alterado:                  não
Execution Worker:              false
AI execution_authorized:       false
executor real chamado:         não
```

## Observação arquitetural

O `PaperStage` atual produz relatórios simulados no contexto do Pipeline, mas não reserva `PaperWallet`, não persiste posições e não grava o histórico legado. Nesta fase isso é tratado como uma proteção de isolamento e é verificado explicitamente.

Uma fase posterior poderá implementar uma conta paper persistente, desde que continue completamente separada do OMS live.
