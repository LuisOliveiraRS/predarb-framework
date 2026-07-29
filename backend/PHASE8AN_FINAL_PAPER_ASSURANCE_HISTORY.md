# PredArb — Fase 8AN: Histórico da Garantia Operacional Final Paper

A Fase 8AN persiste cada avaliação produzida pelo Centro de Garantia
Operacional Final da Fase 8AM.

## Estados registrados

```text
ASSURED
WARNING
BLOCKED
NO_DATA
```

## Recursos

- captura manual e confirmada;
- evolução do score de garantia;
- contagem por estado;
- score médio, melhor e pior;
- sequência atual;
- maior sequência `ASSURED`;
- quantidade de transições;
- dashboard com gráfico SVG;
- exportações CSV e JSON;
- gravação JSON atômica;
- retenção máxima configurável.

## Rotas

- `GET /paper/final-assurance/history/health`
- `GET /paper/final-assurance/history/summary`
- `GET /paper/final-assurance/history/latest`
- `GET /paper/final-assurance/history/entries`
- `GET /paper/final-assurance/history/snapshot`
- `POST /paper/final-assurance/history/capture`
- `GET /paper/final-assurance/history/dashboard`
- `GET /paper/final-assurance/history/export.csv`
- `GET /paper/final-assurance/history/export.json`

## Confirmação obrigatória

```text
CAPTURE-FINAL-PAPER-ASSURANCE
```

## Persistência

```text
paper_data/final_paper_assurance_history.json
```

Variável opcional:

```env
PAPER_FINAL_ASSURANCE_HISTORY_PATH=paper_data/final_paper_assurance_history.json
```

## Segurança

- nenhuma captura automática;
- nenhuma inicialização de runtime;
- nenhuma autorização da próxima fase;
- nenhuma execução live ou financeira;
- nenhuma ordem;
- o histórico não modifica os componentes avaliados;
- todas as guardas precisam permanecer explicitamente bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8an_final_paper_assurance_history.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_operational_assurance_history.py
python -m pytest -q
```

Com os 307 testes anteriores, a expectativa é de 315 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8an_final_paper_assurance_history_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-assurance/history/dashboard
```
