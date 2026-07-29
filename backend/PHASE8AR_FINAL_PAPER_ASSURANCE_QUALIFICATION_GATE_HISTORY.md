# PredArb — Fase 8AR: Histórico do Gate de Qualificação Final Paper

A Fase 8AR persiste cada avaliação produzida pelo Gate de Qualificação da
Garantia Final Paper da Fase 8AQ.

## Estados registrados

```text
QUALIFIED
PENDING
BLOCKED
NO_DATA
```

## Recursos

- captura manual e confirmada;
- evolução do score de qualificação;
- contagem por estado;
- score médio, melhor e pior;
- sequência atual;
- maior sequência `QUALIFIED`;
- quantidade de transições;
- dashboard com gráfico SVG;
- exportações CSV e JSON;
- gravação JSON atômica;
- retenção máxima configurável.

## Rotas

- `GET /paper/final-assurance/qualification-gate/history/health`
- `GET /paper/final-assurance/qualification-gate/history/summary`
- `GET /paper/final-assurance/qualification-gate/history/latest`
- `GET /paper/final-assurance/qualification-gate/history/entries`
- `GET /paper/final-assurance/qualification-gate/history/snapshot`
- `POST /paper/final-assurance/qualification-gate/history/capture`
- `GET /paper/final-assurance/qualification-gate/history/dashboard`
- `GET /paper/final-assurance/qualification-gate/history/export.csv`
- `GET /paper/final-assurance/qualification-gate/history/export.json`

## Confirmação obrigatória

```text
CAPTURE-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE
```

## Persistência

```text
paper_data/final_paper_assurance_qualification_gate_history.json
```

Variável opcional:

```env
PAPER_FINAL_ASSURANCE_GATE_HISTORY_PATH=paper_data/final_paper_assurance_qualification_gate_history.json
```

## Segurança

- nenhuma captura automática;
- nenhuma inicialização de runtime;
- nenhuma autorização da próxima fase;
- nenhuma execução live ou financeira;
- nenhuma ordem;
- o histórico não modifica o gate avaliado;
- o status `QUALIFIED` não autoriza execução real;
- todas as guardas precisam permanecer explicitamente bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ar_final_paper_assurance_qualification_gate_history.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_assurance_qualification_gate_history.py
python -m pytest -q
```

A Fase 8AR adiciona 8 testes. Considerando os 338 testes anteriores, a
expectativa é de 346 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8ar_final_paper_assurance_qualification_gate_history_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-assurance/qualification-gate/history/dashboard
```
