"""Erros do domínio de arbitragem cripto.

Toda condição de incerteza deve virar erro explícito. O domínio é
fail-closed: na dúvida, a oportunidade não é executável.
"""


class CryptoArbitrageError(Exception):
    """Erro base do bounded context cripto."""


class DomainValidationError(CryptoArbitrageError):
    """Valor inválido para um modelo do domínio."""


class PrecisionError(DomainValidationError):
    """Uso de float onde apenas Decimal é aceito."""


class SymbolNormalizationError(CryptoArbitrageError):
    """Símbolo impossível de normalizar entre venues."""


class FeeUnknownError(CryptoArbitrageError):
    """Taxa efetiva desconhecida para o par consultado.

    Invariante 15 da seção 8 do CLAUDE.md: taxa desconhecida
    invalida a oportunidade.
    """


class StaleMarketDataError(CryptoArbitrageError):
    """Book além da idade máxima tolerada.

    Invariante 14 da seção 8 do CLAUDE.md: book stale não pode
    gerar ordem.
    """


class InsufficientDepthError(CryptoArbitrageError):
    """Profundidade insuficiente para a quantidade solicitada."""


class BookNotReadyError(CryptoArbitrageError):
    """Delta recebido antes do snapshot inicial.

    Aplicar delta sobre book vazio produziria um livro
    incompleto que parece válido.
    """


class SequenceGapError(CryptoArbitrageError):
    """Descontinuidade na sequência de updates do book.

    Um gap significa que ao menos um delta se perdeu. O book
    local deixa de refletir a venue e precisa de resync.
    """


class CorruptedBookError(CryptoArbitrageError):
    """Book local em estado impossível, como mercado cruzado.

    Indica que a aplicação de deltas divergiu da venue. Exige
    resync, nunca correção local.
    """


class ConnectorError(CryptoArbitrageError):
    """Falha genérica de conector."""


class ConnectorAlreadyRegisteredError(ConnectorError):
    """Já existe conector registrado com o mesmo identificador."""


class ConnectorNotFoundError(ConnectorError):
    """Nenhum conector registrado para o identificador pedido."""


class ExecutionNotAuthorizedError(CryptoArbitrageError):
    """Tentativa de registrar ou usar capacidade de execução.

    A Fase 18 é read-only. Nenhum adapter de execução pode ser
    registrado, e nenhuma ordem pode ser submetida.
    """
