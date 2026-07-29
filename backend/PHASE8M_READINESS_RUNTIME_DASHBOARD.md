# PredArb — Fase 8M: Dashboard do Runtime de Readiness

A Fase 8M adiciona uma interface web para controlar e acompanhar o runtime
criado na Fase 8L.

## Novas rotas

- `GET /paper/readiness/runtime/dashboard`
- `GET /paper/readiness/runtime/snapshot`

## Recursos

- estado atual do runtime;
- status e score do Readiness Gate;
- contadores de READY, NOT_READY e INSUFFICIENT_DATA;
- total de avaliações persistidas;
- início com intervalo configurável;
- parada manual;
- avaliação imediata;
- reset apenas das estatísticas do runtime;
- visualização do último ciclo.

## Segurança

- o snapshot não inicia o runtime;
- todas as ações exigem confirmação;
- o intervalo mínimo permanece em 30 segundos;
- nenhuma ordem ou sessão Paper é iniciada;
- somente avaliações de readiness são persistidas;
- execução live e financeira permanecem bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8m_readiness_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_readiness_runtime_dashboard.py
python -m pytest -q
```

Com os 106 testes anteriores, a expectativa é de 112 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8m_readiness_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/readiness/runtime/dashboard
```
