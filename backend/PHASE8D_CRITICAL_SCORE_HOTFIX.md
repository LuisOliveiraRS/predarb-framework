# Hotfix da Fase 8D — coerência do score crítico

O teste revelou uma inconsistência de fronteira:

- alerta crítico: penalidade de 30 pontos;
- taxa de sucesso de 90%: bônus de 5 pontos;
- score final: 75;
- status: `CRITICAL`.

Um estado crítico não deve permanecer na faixa de score saudável. O hotfix
mantém o cálculo anterior, mas limita o score a no máximo 74 quando existe
qualquer alerta de severidade `critical`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8d_critical_score_hotfix.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_performance_monitor.py
python -m pytest -q
```

Resultados esperados:

```text
7 passed
46 passed
```
