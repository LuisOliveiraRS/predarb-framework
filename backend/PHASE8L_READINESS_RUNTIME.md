# PredArb — Fase 8L: Runtime controlado do Readiness

A Fase 8L automatiza avaliações periódicas do Paper Readiness Gate e registra
cada resultado no histórico da Fase 8K.

## Novas rotas

- `GET /paper/readiness/runtime/health`
- `GET /paper/readiness/runtime/status`
- `GET /paper/readiness/runtime/last-cycle`
- `POST /paper/readiness/runtime/cycle`
- `POST /paper/readiness/runtime/start`
- `POST /paper/readiness/runtime/stop`
- `POST /paper/readiness/runtime/reset-statistics`

## Confirmações obrigatórias

```text
CAPTURE-PAPER-READINESS
START-PAPER-READINESS-RUNTIME
STOP-PAPER-READINESS-RUNTIME
RESET-PAPER-READINESS-RUNTIME
```

## Segurança

- o runtime não inicia automaticamente;
- o intervalo mínimo pela API é de 30 segundos;
- nenhuma ordem é enviada;
- nenhuma sessão Paper é iniciada;
- nenhum incidente é modificado;
- somente o histórico de readiness é atualizado;
- execução live e financeira permanecem bloqueadas.

## Variáveis opcionais

```env
PAPER_READINESS_RUNTIME_ENABLED=true
PAPER_READINESS_RUNTIME_INTERVAL_SECONDS=300
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8l_readiness_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_readiness_runtime.py
python -m pytest -q
```

Com os 97 testes anteriores, a expectativa é de 106 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8l_readiness_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
