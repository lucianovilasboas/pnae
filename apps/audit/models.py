from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    """Trilha de auditoria imutável (RN-11).

    Eventos nunca são alterados nem apagados pela aplicação. `metadata_json`
    guarda apenas o necessário — nunca token QR nem dado pessoal excessivo.
    """

    campus = models.ForeignKey(
        "campus.Campus",
        on_delete=models.PROTECT,
        related_name="audit_events",
        verbose_name="campus",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="audit_events",
        verbose_name="autor",
        null=True,
        blank=True,
    )
    action = models.CharField("ação", max_length=80)
    entity_type = models.CharField("entidade", max_length=80)
    entity_id = models.CharField("id da entidade", max_length=64)
    occurred_at = models.DateTimeField("ocorrido em", default=timezone.now)
    metadata_json = models.JSONField("metadados", default=dict, blank=True)

    class Meta:
        verbose_name = "evento de auditoria"
        verbose_name_plural = "eventos de auditoria"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["campus", "occurred_at"], name="idx_audit_campus_time"),
            models.Index(fields=["entity_type", "entity_id"], name="idx_audit_entity"),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id}"
