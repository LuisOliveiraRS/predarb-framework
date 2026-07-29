# PredArb — Hotfix de Runtime da Fase 3

Este hotfix corrige:

1. interpolação inválida em PowerShell na mensagem `Mercados duplicados em ${Context}: ...`;
2. compatibilidade dos scripts com Windows PowerShell 5.1 por meio de UTF-8 com BOM;
3. inicialização confiável da Fase 3 com `phase3_start_server.ps1`, que define todas as variáveis no mesmo processo que inicia o Uvicorn e recusa iniciar quando a porta já está ocupada.

O backend em `app/` não é alterado.
