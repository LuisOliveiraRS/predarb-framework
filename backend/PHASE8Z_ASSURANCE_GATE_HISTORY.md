# PredArb — Fase 8Z: Histórico do Gate de Qualificação Paper

A Fase 8Z persiste as avaliações produzidas pelo Gate de Qualificação da
Fase 8Y e acompanha sua evolução ao longo do tempo.

## Recursos

- captura manual e confirmada;
- persistência JSON com gravação atômica;
- contagem por status;
- score médio, melhor e pior score;
- sequência atual;
- maior sequência `QUALIFIED`;
- quantidade de transições;
- armazenamento dos códigos de falha;
- gráfico SVG do score;
- dashboard;
- exportação CSV.

## Novas rotas

- `GET /paper/certification/assurance/gate/history/health`
- `GET /paper/certification/assurance/gate/history/summary`
- `GET /paper/certification/assurance/gate/history/latest`
- `GET /paper/certification/assurance/gate/history/entries`
- `GET /paper/certification/assurance/gate/history/snapshot`
- `POST /paper/certification/assurance/gate/history/capture`
- `GET /paper/certification/assurance/gate/history/dashboard`
- `GET /paper/certification/assurance/gate/history/export.csv`

## Confirmação obrigatória

```text
CAPTURE-PAPER-ASSURANCE-QUALIFICATION
```

## Arquivo persistente

```text
paper_data/paper_assurance_qualification_history.json
```

Variável opcional:

```env
PAPER_ASSURANCE_GATE_HISTORY_PATH=paper_data/paper_assurance_qualification_history.json
```

Não é necessário alterar o `.env`.

## Segurança

- nenhuma captura ocorre ao abrir o dashboard;
- endpoints GET não alteram o histórico;
- a captura registra apenas o relatório do gate;
- não inicia runtimes;
- não cria autorização financeira;
- não envia ordens;
- não altera o modo live.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8z_assurance_gate_history.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_assurance_gate_history.py
python -m pytest -q
```

Com os 201 testes anteriores, a expectativa é de 209 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8z_assurance_gate_history_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/assurance/gate/history/dashboard
```
