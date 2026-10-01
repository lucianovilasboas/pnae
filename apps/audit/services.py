"""Gravação da trilha de auditoria (RN-11).

Um único ponto de entrada para eventos, para garantir formato consistente e
evitar vazamento de dados: os `metadata` devem conter apenas o necessário,
nunca token QR nem dado pessoal excessivo.
"""

from .models import AuditEvent


def record_event(*, action, entity_type, entity_id, actor=None, campus=None, metadata=None):
    return AuditEvent.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor=actor if getattr(actor, "pk", None) else None,
        campus=campus,
        metadata_json=metadata or {},
    )
