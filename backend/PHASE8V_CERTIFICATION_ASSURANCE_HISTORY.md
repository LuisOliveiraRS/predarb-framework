# PredArb — Fase 8V: Histórico do Centro de Garantia Paper

A Fase 8V persiste snapshots do Centro de Garantia criado na Fase 8U e
acompanha sua evolução ao longo do tempo.

## Recursos

- captura manual e confirmada;
- persistência JSON com gravação atômica;
- contagem por status;
- score médio, melhor e pior score;
- sequência atual;
- maior sequência `ASSURED`;
- quantidade de transições;
- gráfico SVG do score;
- dashboard;
- exportação CSV.

## Novas rotas

- `GET /paper/certification/assurance/history/health`
- `GET /paper/certification/assurance/history/summary`
- `GET /paper/certification/assurance/history/latest`
- `GET /paper/certification/assurance/history/entries`
- `GET /paper/certification/assurance/history/snapshot`
- `POST /paper/certification/assurance/history/capture`
- `GET /paper/certification/assurance/history/dashboard`
- `GET /paper/certification/assurance/history/export.csv`

## Confirmação obrigatória

```text
CAPTURE-PAPER-CERTIFICATION-ASSURANCE
```

## Arquivo persistente

```text
paper_data/paper_certification_assurance_history.json
```

Variável opcional:

```env
PAPER_ASSURANCE_HISTORY_PATH=paper_data/paper_certification_assurance_history.json
```

Não é necessário alterar o `.env`.

## Segurança

- nenhuma captura ocorre ao abrir o dashboard;
- o snapshot GET não altera o histórico;
- a captura registra somente o estado atual;
- não inicia nenhum runtime;
- não cria evidências financeiras;
- não envia ordens;
- não autoriza execução live.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8v_certification_assurance_history.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_assurance_history.py
python -m pytest -q
```

Com os 172 testes anteriores, a expectativa é de 179 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8v_certification_assurance_history_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/assurance/history/dashboard
```
