"""Mixin de admin que registra alterações na trilha de auditoria (RN-11)."""

from .services import record_event


class AuditedAdminMixin:
    """Grava `AuditEvent` em criação, edição e exclusão feitas pelo admin."""

    def _audit_campus(self, obj):
        return getattr(obj, "campus", None)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(
            action="admin.updated" if change else "admin.created",
            entity_type=obj._meta.model_name,
            entity_id=obj.pk,
            actor=request.user,
            campus=self._audit_campus(obj),
            metadata={"model": obj._meta.label},
        )

    def delete_model(self, request, obj):
        entity_id = obj.pk
        model_label = obj._meta.label
        entity = obj._meta.model_name
        campus = self._audit_campus(obj)
        super().delete_model(request, obj)
        record_event(
            action="admin.deleted",
            entity_type=entity,
            entity_id=entity_id,
            actor=request.user,
            campus=campus,
            metadata={"model": model_label},
        )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)
