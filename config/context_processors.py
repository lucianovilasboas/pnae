"""Context processors do projeto."""

from config.version import APP_VERSION


def app_version(request):
    """Expõe a versão do app aos templates (rodapé e menu mobile)."""
    return {"app_version": APP_VERSION}
