"""Erros seguros da camada de autenticacao."""


class AuthenticationError(Exception):
    """Erro base que pode ser convertido em resposta HTTP segura."""


class AuthConfigurationError(AuthenticationError):
    """Configuracao de autenticacao incompleta ou desabilitada."""


class InvalidAccessTokenError(AuthenticationError):
    """Token ausente, invalido, expirado ou emitido por outra origem."""


class MFARequiredError(AuthenticationError):
    """Operacao exige uma sessao autenticada no nivel AAL2."""

class ProfileLookupError(AuthenticationError):
    """Nao foi possivel consultar o perfil autorizado."""


class InactiveUserError(AuthenticationError):
    """Usuario autenticado, mas desativado no PredArb."""


class InvalidProfileError(AuthenticationError):
    """Perfil inexistente, inconsistente ou com papel invalido."""


class InsufficientRoleError(AuthenticationError):
    """Usuario nao possui o papel exigido para a operacao."""

class InvalidCredentialsError(AuthenticationError):
    """E-mail ou senha recusados pelo provedor de identidade."""


class SessionRefreshError(AuthenticationError):
    """Nao foi possivel renovar a sessao autenticada."""


class AuthProviderError(AuthenticationError):
    """Falha temporaria no provedor de autenticacao."""
