# PredArb Fase 7 — Hotfix de rotas da aplicação

Este hotfix restaura o `app/core/application.py` consolidado da Fase 7.

Ele registra os routers oficiais, incluindo:

- `/ws/router`
- `/paper/risk/status`
- `/paper/session/status`
- `/paper/session/report`
- `/paper/session/cycle`
- `/paper/session/start`
- `/paper/session/stop`
- `/paper/session/reset-report`

Também preserva o lifecycle da conta Paper e da sessão Paper.
