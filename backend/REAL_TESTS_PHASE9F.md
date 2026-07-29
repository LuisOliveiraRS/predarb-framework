# PredArb ? Fase 9F: Shadow Runtime e valida??o operacional

A Fase 9F adiciona ciclos operacionais controlados de Shadow Execution sobre
dados reais de mercado em modo somente leitura.

O runtime avalia exclusivamente correspond?ncias confirmadas manualmente,
seleciona apenas oportunidades classificadas como `PROFITABLE` e encaminha
essas oportunidades ao simulador da Fase 9E.

Nenhuma ordem financeira real ? criada ou enviada.

## Objetivos

- executar ciclos Shadow controlados;
- usar dados reais de mercado somente para leitura;
- processar apenas matches confirmados manualmente;
- encaminhar somente oportunidades `PROFITABLE`;
- registrar m?tricas operacionais em mem?ria;
- medir dura??o, rejei??es e erros;
- impedir ciclos simult?neos;
- permitir integra??o opt-in com o scheduler;
- disponibilizar endpoints somente `GET`;
- preservar integralmente a conta Paper;
- manter a auditoria desabilitada por padr?o.

## Componentes

    app/paper/shadow_execution_runtime.py
    app/api/routers/shadow_execution_runtime.py
    app/scheduler/tasks.py
    app/core/settings.py
    app/core/application.py
    tests/test_shadow_execution_runtime.py
    tests/test_application_integration.py

## Fluxo operacional

    matches confirmados manualmente
            |
            v
    EconomicOpportunityEngine
            |
            | somente PROFITABLE
            v
    ShadowExecutionRuntime
            |
            v
    ShadowExecutionSimulator
            |
            v
    resultados simulados e m?tricas em mem?ria

O Shadow Runtime n?o confirma matches automaticamente e n?o modifica a conta
Paper.

## Configura??o padr?o

    SHADOW_RUNTIME_ENABLED=true
    SHADOW_RUNTIME_SCHEDULER_ENABLED=false
    SHADOW_RUNTIME_INTERVAL_SECONDS=60
    SHADOW_RUNTIME_MAX_OPPORTUNITIES_PER_CYCLE=10
    SHADOW_RUNTIME_FORCE_REFRESH=false
    SHADOW_RUNTIME_PERSIST_AUDIT=false

O runtime pode ser consultado pela API, mas o agendamento autom?tico permanece
desabilitado por padr?o.

## Guardas fail-closed

As seguintes configura??es s?o rejeitadas:

- scheduler Shadow ativo com `SHADOW_RUNTIME_ENABLED=false`;
- scheduler Shadow ativo com `SCHEDULER_ENABLED=false`;
- persist?ncia autom?tica de auditoria ativa;
- intervalo inferior a 10 segundos;
- limite de oportunidades igual ou inferior a zero.

## Integra??o com o scheduler

Quando explicitamente habilitado, o lifespan registra:

    market_update_task
    shadow_runtime_task

O APScheduler utiliza:

    max_instances=1
    coalesce=true
    misfire_grace_time=30

O runtime tamb?m possui bloqueio n?o bloqueante contra sobreposi??o de ciclos.

No encerramento da aplica??o:

    scheduler_connected=false
    shadow_runtime_scheduler=false

## Status poss?veis

    SKIPPED_ALREADY_RUNNING
    NO_CONFIRMED_MATCHES
    NO_OPPORTUNITIES
    NO_PROFITABLE_OPPORTUNITIES
    COMPLETED
    COMPLETED_WITH_ERRORS
    FAILED

Falhas individuais de simula??o s?o isoladas e contabilizadas sem autorizar
execu??o financeira.

## Endpoints de observabilidade

    GET /real-markets/shadow-runtime/health
    GET /real-markets/shadow-runtime/status
    GET /real-markets/shadow-runtime/metrics
    GET /real-markets/shadow-runtime/last-cycle
    GET /real-markets/shadow-runtime/architecture

N?o existem m?todos `POST`, `PUT`, `PATCH` ou `DELETE` na API da Fase 9F.

Tamb?m n?o existe endpoint para iniciar ciclos, confirmar matches, alterar
configura??es, enviar ordens ou modificar a conta Paper.

## Flags protegidas

As seguintes flags permanecem sempre `false`:

    paper_execution_authorized
    live_authorization
    execution_authorized
    live_execution
    financial_execution
    next_step_authorized
    automatic_execution_authorized
    order_submission_available

Tamb?m permanecem desabilitados:

    paper_account_mutation
    wallet_access
    credential_access

## Testes focados

Comando:

    python -m pytest tests/test_application_integration.py tests/test_shadow_execution_runtime.py -q

Resultado validado:

    18 passed

## Regress?o Shadow

Comando:

    python -m pytest tests/test_shadow_execution.py tests/test_shadow_execution_runtime.py tests/test_application_integration.py -q

Resultado validado:

    33 passed

## Su?te completa

Comando:

    python -m pytest -q

Resultado validado:

    455 passed

## Smoke test HTTP

Os cinco endpoints da Fase 9F responderam HTTP `200`.

Contrato confirmado:

    5 endpoints aprovados
    somente m?todos GET
    todas as flags financeiras false
    auditoria Shadow n?o modificada
    conta Paper n?o modificada

O arquivo abaixo n?o foi criado durante a valida??o:

    paper_data/shadow_execution_audit.jsonl

A conta Paper manteve o mesmo tamanho e o mesmo hash SHA-256 antes e depois do
smoke test.

## Auditoria est?tica

A auditoria do c?digo introduzido pela Fase 9F confirmou:

    m?dulos live introduzidos: nenhum
    identificadores live novos: nenhum
    imports de exchanges: nenhum
    imports de OMS: nenhum
    imports de trading: nenhum
    erros de whitespace: nenhum

O import preexistente `app.orders.execution_worker` no arquivo
`app/core/application.py` n?o foi introduzido pela Fase 9F.

## Isolamento operacional

A Fase 9F n?o utiliza:

- credenciais privadas;
- chaves privadas;
- carteiras;
- adaptadores de execu??o;
- OMS;
- submiss?o de ordens;
- execu??o financeira;
- confirma??o autom?tica de mercados;
- muta??o da conta Paper.

## Crit?rios de aprova??o

A Fase 9F ? considerada aprovada quando:

- os cinco endpoints respondem `200`;
- todos os endpoints permanecem somente `GET`;
- o scheduler Shadow fica desabilitado por padr?o;
- a persist?ncia autom?tica permanece bloqueada;
- somente oportunidades `PROFITABLE` s?o simuladas;
- ciclos simult?neos s?o rejeitados;
- a conta Paper n?o ? modificada;
- nenhum arquivo de auditoria ? criado por consultas HTTP;
- todas as flags financeiras permanecem `false`;
- a su?te completa do projeto ? aprovada.

## Estado final

    Fase: 9F
    Shadow Runtime: READY
    Scheduler Shadow padr?o: DISABLED
    Persist?ncia autom?tica: DISABLED
    Execu??o financeira: DISABLED
    Submiss?o de ordens: UNAVAILABLE
    Conta Paper: UNCHANGED
    Auditoria est?tica: APPROVED
    Su?te completa: 455 PASSED
