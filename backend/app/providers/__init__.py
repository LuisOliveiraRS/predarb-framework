"""
Providers responsáveis por integrar plataformas externas.

Um Provider conhece a API da plataforma.

Ele sabe:

- quais endpoints utilizar;
- como montar payloads;
- como tratar erros;
- como combinar respostas.

O restante da aplicação nunca conversa
diretamente com APIs externas.
"""