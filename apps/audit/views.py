from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_date

from apps.accounts.models import UserRole

from .models import AuditEvent


def healthcheck(request):
    """Sonda simples de saúde: processo vivo e banco acessível."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database_ok = True
    except Exception:  # pragma: no cover - depende do ambiente
        database_ok = False

    return JsonResponse(
        {"status": "ok" if database_ok else "error", "database": database_ok},
        status=200 if database_ok else 503,
    )


@login_required
def audit_list(request):
    user = request.user
    if not (user.is_superuser or user.role in {UserRole.ADMIN, UserRole.MANAGER}):
        raise PermissionDenied

    queryset = AuditEvent.objects.select_related("actor", "campus")
    if user.campus_id and not user.is_superuser:
        queryset = queryset.filter(campus_id=user.campus_id)

    action = request.GET.get("action", "").strip()
    entity_type = request.GET.get("entity", "").strip()
    actor = request.GET.get("actor", "").strip()
    date_from = parse_date(request.GET.get("from", "") or "")
    date_to = parse_date(request.GET.get("to", "") or "")

    if action:
        queryset = queryset.filter(action=action)
    if entity_type:
        queryset = queryset.filter(entity_type=entity_type)
    if actor:
        queryset = queryset.filter(actor__email__icontains=actor)
    if date_from:
        queryset = queryset.filter(occurred_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(occurred_at__date__lte=date_to)

    events = queryset.order_by("-occurred_at")[:200]
    return render(
        request,
        "audit/list.html",
        {
            "events": events,
            "actions": sorted(
                AuditEvent.objects.values_list("action", flat=True).distinct()
            ),
            "entities": sorted(
                AuditEvent.objects.values_list("entity_type", flat=True).distinct()
            ),
            "filters": {
                "action": action,
                "entity": entity_type,
                "actor": actor,
                "from": request.GET.get("from", ""),
                "to": request.GET.get("to", ""),
            },
            "breadcrumbs": [
                {"label": "Início", "url": "/"},
                {"label": "Auditoria"},
            ],
        },
    )
