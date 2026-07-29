# PredArb — Fase 8H: dashboard de controle do runtime

A Fase 8H adiciona um painel web sobre o runtime controlado criado na Fase 8G.

## Novas rotas

- `GET /paper/performance/incidents/runtime/dashboard`
- `GET /paper/performance/incidents/runtime/snapshot`

## Controles disponíveis no painel

- iniciar runtime com intervalo configurável;
- parar runtime;
- executar captura manual;
- resetar estatísticas do runtime;
- consultar último ciclo;
- acompanhar incidentes e score do monitor.

O painel utiliza os endpoints administrativos da Fase 8G e preserva todas as
confirmações obrigatórias.

## Segurança

- início manual obrigatório;
- nenhuma execução de trades;
- nenhuma ordem financeira;
- nenhuma autorização da IA;
- snapshot não inicia o runtime implicitamente;
- execução live e financeira permanecem `false`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8h_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_performance_incident_runtime_dashboard.py
python -m pytest -q
```

Com os 68 testes anteriores, a expectativa é de 74 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8h_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/performance/incidents/runtime/dashboard
```
