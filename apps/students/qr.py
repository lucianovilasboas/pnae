"""Geração do QR Code do estudante.

O conteúdo do QR é a **matrícula** do estudante (identificador único na
instituição e dentro do campus). O PNG é gerado em memória; a matrícula não é
segredo, então nada é persistido além do próprio `registration_number`.
"""

import base64
import io

import qrcode

from .models import Student


def qr_png_bytes(data: str) -> bytes:
    image = qrcode.make(data)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def qr_data_uri(data: str) -> str:
    encoded = base64.b64encode(qr_png_bytes(data)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def students_for_qr(campus, class_group=None):
    queryset = Student.objects.filter(campus=campus, active=True).select_related("class_group")
    if class_group is not None:
        queryset = queryset.filter(class_group=class_group)
    return list(queryset.order_by("full_name"))
