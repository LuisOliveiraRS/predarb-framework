"""Manutenção de dados de mercado em tempo real.

Lógica pura: nenhum módulo aqui abre conexão. Os conectores das
fases seguintes traduzem seus payloads para os tipos deste
pacote, que cuidam de sequência, gap, frescor e latência.
"""
