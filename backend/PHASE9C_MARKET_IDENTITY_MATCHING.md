# PredArb — Fase 9C: Identidade e Correspondência de Mercados

A Fase 9C cria a camada que identifica quando mercados de plataformas
diferentes podem representar o mesmo evento econômico.

Ela não executa arbitragem e não ativa pares automaticamente.

## Objetivos

- normalizar títulos;
- remover diferenças superficiais de idioma e pontuação;
- criar fingerprints estáveis;
- normalizar outcomes equivalentes, como `Sim/Não` e `Yes/No`;
- comparar datas de fechamento;
- comparar categorias;
- calcular um score explicável;
- gerar candidatos entre conectores diferentes;
- permitir confirmação manual persistente;
- rejeitar pares estruturalmente incompatíveis.

## Componentes

```text
app/real_markets/matching.py
app/api/routers/market_matching.py
tests/test_market_identity_matching.py
```

## Score de correspondência

Pesos padrão:

```text
Título normalizado:       60%
Estrutura dos outcomes:   20%
Data de fechamento:       15%
Categoria:                 5%
```

Estados:

```text
STRONG_CANDIDATE
CANDIDATE
REJECTED
```

Limiares padrão:

```env
REAL_MARKET_MATCH_CANDIDATE_THRESHOLD=0.55
REAL_MARKET_MATCH_STRONG_THRESHOLD=0.80
```

Um candidato nunca é ativado automaticamente.

## Fingerprint

O fingerprint SHA-256 utiliza:

- título normalizado;
- data de fechamento;
- assinatura dos outcomes;
- categoria normalizada.

O identificador da plataforma e o ID do mercado não entram no hash,
permitindo comparar representações do mesmo evento em conectores distintos.

## Correspondências manuais

Persistência padrão:

```text
paper_data/real_market_manual_matches.json
```

Variável opcional:

```env
REAL_MARKET_MANUAL_MATCHES_PATH=paper_data/real_market_manual_matches.json
```

Confirmações obrigatórias:

```text
CONFIRM-REAL-MARKET-MATCH
REMOVE-REAL-MARKET-MATCH
```

Uma correspondência manual registra somente configuração de equivalência.
Ela não habilita execução, saldo ou envio de ordens.

## Rotas

```text
GET    /real-markets/matching/health
GET    /real-markets/matching/identities
GET    /real-markets/matching/compare
GET    /real-markets/matching/candidates
GET    /real-markets/matching/manual-matches
POST   /real-markets/matching/manual-matches
DELETE /real-markets/matching/manual-matches/{match_id}
GET    /real-markets/matching/dashboard
GET    /real-markets/matching/architecture
```

## Dashboard

```text
http://127.0.0.1:8000/real-markets/matching/dashboard
```

O painel permite:

- escolher dois conectores;
- limitar a quantidade de mercados;
- gerar candidatos;
- visualizar cada componente do score;
- confirmar um par manualmente;
- remover uma confirmação;
- acompanhar os pares persistidos.

## Segurança

```json
{
  "market_data_only": true,
  "automatic_matching_authorized": false,
  "paper_execution_authorized": false,
  "live_authorization": false,
  "execution_authorized": false,
  "live_execution": false,
  "financial_execution": false,
  "next_step_authorized": false
}
```

A fase não possui:

- execução automática;
- criação ou cancelamento de ordens;
- acesso a carteira;
- leitura ou movimentação de saldo;
- chaves privadas;
- credenciais de trading;
- runtime em background.

## Instalação

Execute dentro de:

```text
C:\predarb-framework\backend
```

Comando:

```powershell
python ".\scripts\real_tests\install_phase9c_market_identity_matching.py"
```

As Fases 9A e 9B precisam estar instaladas.

## Testes

```powershell
python -m pytest -q tests\test_market_identity_matching.py
python -m pytest -q
```

A Fase 9C adiciona 13 testes.

Considerando os 399 testes esperados até a Fase 9B, a expectativa passa
a ser de 412 testes aprovados. O resultado do terminal do projeto é a
confirmação efetiva.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase9c_market_identity_matching_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

O checker:

- valida o serviço de matching;
- gera identidades para mock e Polymarket;
- compara um par;
- gera a matriz de candidatos;
- consulta correspondências manuais;
- valida dashboard e arquitetura.

Ele não cria correspondências persistentes.

## Próxima fase funcional

A Fase 9D deverá transformar pares confirmados em oportunidades
econômicas simuladas, considerando:

- melhor ask de cada outcome;
- profundidade disponível;
- taxas configuráveis;
- slippage estimado;
- custo total;
- lucro bruto e líquido;
- tamanho máximo executável;
- rejeição de dados antigos.

Ainda sem envio de ordens.
