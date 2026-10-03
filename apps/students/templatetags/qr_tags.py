"""Tags de template para o QR de impressão."""

from django import template
from django.utils.safestring import mark_safe

from ..qr import qr_svg as _qr_svg

register = template.Library()


@register.filter
def qr_svg(value):
    """Renderiza o SVG (inline) do QR cujo conteúdo é o valor informado."""
    return mark_safe(_qr_svg(str(value)))
