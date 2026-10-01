"""Geração de QR Code e atribuição de tokens.

O PNG é gerado em memória a partir do token bruto. O token bruto só existe no
momento da atribuição/exportação; o banco guarda apenas o hash (ver
docs/02-modelo-dados.md §5).
"""

import base64
import io

import qrcode

from .models import Student
from .tokens import generate_token, hash_token


def qr_png_bytes(data: str) -> bytes:
    image = qrcode.make(data)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def qr_data_uri(data: str) -> str:
    encoded = base64.b64encode(qr_png_bytes(data)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def assign_tokens(students):
    """Gera novo token para cada estudante e guarda o hash.

    Retorna uma lista de `(student, token)`. O token bruto é retornado apenas
    aqui — quem chama deve exibi-lo/impirmi-lo e descartá-lo.

    ATENÇÃO: rotaciona o token de quem já tinha um; QRs antigos deixam de valer.
    """
    generated = []
    for student in students:
        token = generate_token()
        student.qr_token_hash = hash_token(token)
        student.save(update_fields=["qr_token_hash", "updated_at"])
        generated.append((student, token))
    return generated


def students_for_qr(campus, class_group=None, only_missing=False):
    queryset = Student.objects.filter(campus=campus, active=True).select_related("class_group")
    if class_group is not None:
        queryset = queryset.filter(class_group=class_group)
    if only_missing:
        queryset = queryset.filter(qr_token_hash="")
    return list(queryset.order_by("full_name"))
