# PredArb — Reparo forçado de rotas da Fase 7

Este pacote mantém o `application.py` canônico em `repair_payload` e inclui um script que:

1. confirma a raiz do backend;
2. cria backup do `application.py` atual;
3. copia forçadamente o arquivo canônico;
4. remove `__pycache__`;
5. confirma o caminho do módulo importado;
6. valida WebSocket, Dashboard e rotas Paper.
