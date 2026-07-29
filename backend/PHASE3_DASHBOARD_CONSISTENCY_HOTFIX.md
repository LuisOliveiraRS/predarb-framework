# PredArb Phase 3 — Dashboard Consistency Hotfix

Este hotfix altera somente `scripts/real_tests/phase3_server_smoke.ps1`.

A verificação anterior comparava duas requisições separadas enquanto o Scheduler podia atualizar o `MarketRepository` entre elas. Isso gerava um falso positivo de divergência.

A nova verificação:

1. consulta a versão do repository antes;
2. solicita o snapshot atualizado do Dashboard;
3. consulta `/markets/`;
4. consulta novamente a versão do repository;
5. aceita a amostra somente quando a versão permaneceu estável e todos os contadores coincidem;
6. valida também `dashboard.markets == dashboard.data.markets.Count`;
7. repete até oito vezes em caso de atualização concorrente.

Nenhum arquivo da aplicação é alterado.
