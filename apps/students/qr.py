"""Geração do QR Code do estudante.

O conteúdo do QR é a **matrícula** do estudante (identificador único na
instituição e dentro do campus). Para telas (portal) geramos PNG; para
impressão geramos **SVG** (nítido em qualquer tamanho).
"""

import base64
import io

import qrcode
import qrcode.image.svg

from .models import Student


def qr_png_bytes(data: str) -> bytes:
    image = qrcode.make(data)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def qr_data_uri(data: str) -> str:
    encoded = base64.b64encode(qr_png_bytes(data)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def qr_svg(data: str) -> str:
    """SVG inline (sem a declaração XML) para embutir em HTML de impressão."""
    image = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    image.save(buffer)
    svg = buffer.getvalue().decode("utf-8")
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].lstrip()
    return svg


def students_for_qr(campus, class_group=None, students=None):
    queryset = Student.objects.filter(campus=campus, active=True).select_related("class_group")
    if class_group is not None:
        queryset = queryset.filter(class_group=class_group)
    if students is not None:
        queryset = queryset.filter(pk__in=students)
    return list(queryset.order_by("class_group__name", "full_name"))
