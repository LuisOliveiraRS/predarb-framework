# PredArb — Fase 8K: Histórico e Auditoria do Readiness

A Fase 8K adiciona persistência das avaliações geradas pelo Paper Readiness
Gate da Fase 8J.

## Recursos

- captura manual e confirmada;
- histórico persistente em JSON;
- evolução do score;
- diferença de score entre avaliações;
- contagem de READY, NOT_READY e INSUFFICIENT_DATA;
- sequência atual do mesmo status;
- maior sequência consecutiva de READY;
- número de transições de status;
- dashboard e exportação CSV;
- nenhuma captura implícita;
- nenhuma execução financeira.

## Novas rotas

- `GET /paper/readiness/history/health`
- `GET /paper/readiness/history/summary`
- `GET /paper/readiness/history/latest`
- `GET /paper/readiness/history/entries`
- `GET /paper/readiness/history/snapshot`
- `POST /paper/readiness/history/capture`
- `GET /paper/readiness/history/dashboard`
- `GET /paper/readiness/history/export.csv`

## Confirmação obrigatória

```text
CAPTURE-PAPER-READINESS
```

## Arquivo persistente

```text
paper_data/paper_readiness_history.json
```

Variável opcional:

```env
PAPER_READINESS_HISTORY_PATH=paper_data/paper_readiness_history.json
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8k_readiness_history.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_readiness_history.py
python -m pytest -q
```

Com os 89 testes anteriores, a expectativa é de 97 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8k_readiness_history_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/readiness/history/dashboard
```
