# PredArb — Fase 8AD: Histórico da Validação Final Paper

A Fase 8AD persiste as avaliações produzidas pela Validação Final da Fase 8AC
e acompanha a evolução do estado final do ambiente Paper.

## Recursos

- captura manual e confirmada;
- persistência JSON com gravação atômica;
- validação fail-closed do arquivo persistido;
- contagem por status;
- score médio, melhor e pior;
- sequência atual;
- maior sequência `PAPER_VALIDATED`;
- quantidade de transições;
- armazenamento dos códigos de falha;
- gráfico SVG do score;
- dashboard;
- exportação CSV.

## Novas rotas

- `GET /paper/final-validation/history/health`
- `GET /paper/final-validation/history/summary`
- `GET /paper/final-validation/history/latest`
- `GET /paper/final-validation/history/entries`
- `GET /paper/final-validation/history/snapshot`
- `POST /paper/final-validation/history/capture`
- `GET /paper/final-validation/history/dashboard`
- `GET /paper/final-validation/history/export.csv`

## Confirmação obrigatória

```text
CAPTURE-FINAL-PAPER-VALIDATION
```

## Arquivo persistente

```text
paper_data/final_paper_validation_history.json
```

Variável opcional:

```env
PAPER_FINAL_VALIDATION_HISTORY_PATH=paper_data/final_paper_validation_history.json
```

Não é necessário alterar o `.env`.

## Segurança

- nenhuma captura ocorre ao abrir o dashboard;
- endpoints GET não alteram o histórico;
- a captura registra apenas o relatório da validação final;
- não inicia runtimes;
- não autoriza a próxima fase;
- não habilita execução financeira;
- não envia ordens;
- não altera o modo live.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ad_final_paper_validation_history.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_history.py
python -m pytest -q
```

Com os 231 testes anteriores, a expectativa é de 239 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8ad_final_paper_validation_history_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-validation/history/dashboard
```
