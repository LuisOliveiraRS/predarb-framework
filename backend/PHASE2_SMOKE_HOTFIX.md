# PredArb — Hotfix do smoke test da Fase 2

Corrige a função `Test-Endpoint` para que a saída de `ConvertTo-Json` seja exibida no host sem ser devolvida junto com a resposta HTTP. Também normaliza a lista de connectors antes da validação.

O backend não é alterado por este hotfix.
