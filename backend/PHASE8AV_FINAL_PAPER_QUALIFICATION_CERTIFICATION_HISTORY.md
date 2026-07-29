# PredArb — Fase 8AV: Histórico da Certificação Final Paper

A Fase 8AV persiste cada avaliação produzida pela Certificação da
Qualificação Final Paper da Fase 8AU.

## Estados registrados

```text
CERTIFIED
PENDING
BLOCKED
NO_DATA
```

## Recursos

- captura manual e confirmada;
- evolução do score de certificação;
- contagem por estado;
- score médio, melhor e pior;
- sequência atual;
- maior sequência `CERTIFIED`;
- quantidade de transições;
- dashboard com gráfico SVG;
- exportações CSV e JSON;
- gravação JSON atômica;
- retenção máxima configurável.

## Rotas

- `GET /paper/final-assurance/qualification-certification/history/health`
- `GET /paper/final-assurance/qualification-certification/history/summary`
- `GET /paper/final-assurance/qualification-certification/history/latest`
- `GET /paper/final-assurance/qualification-certification/history/entries`
- `GET /paper/final-assurance/qualification-certification/history/snapshot`
- `POST /paper/final-assurance/qualification-certification/history/capture`
- `GET /paper/final-assurance/qualification-certification/history/dashboard`
- `GET /paper/final-assurance/qualification-certification/history/export.csv`
- `GET /paper/final-assurance/qualification-certification/history/export.json`

## Confirmação obrigatória

```text
CAPTURE-FINAL-PAPER-QUALIFICATION-CERTIFICATION
```

## Persistência

```text
paper_data/final_paper_qualification_certification_history.json
```

Variável opcional:

```env
PAPER_FINAL_QUALIFICATION_CERTIFICATION_HISTORY_PATH=paper_data/final_paper_qualification_certification_history.json
```

## Segurança

- nenhuma captura automática;
- nenhum runtime novo;
- nenhuma autorização da próxima fase;
- nenhuma execução live ou financeira;
- nenhuma ordem;
- o status `CERTIFIED` não autoriza execução real;
- todas as guardas permanecem explicitamente bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8av_final_paper_qualification_certification_history.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_qualification_certification_history.py
python -m pytest -q
```

A Fase 8AV adiciona 8 testes. Considerando os 369 testes anteriores, a
expectativa é de 377 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8av_final_paper_qualification_certification_history_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-assurance/qualification-certification/history/dashboard
```
