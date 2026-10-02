"""Endpoints JSON de distribuição e entrega (docs/03-api.md).

O endpoint mais sensível é `POST /api/distributions/{id}/scan`: ele decide a
entrega regular de forma atômica e é o caminho quente da operação.
"""

import csv
import io
import json

from django.db import IntegrityError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.decorators import (
    api_authorize_required,
    api_login_required,
    api_operator_required,
    api_reverse_required,
)
from apps.campus.selectors import resolve_campus
from apps.students.models import Student
from apps.students.tokens import hash_token

from . import services
from .models import Delivery, Distribution, DistributionStatus
from .services import DistributionStateError


def _payload(request) -> dict:
    if request.content_type == "application/json" and request.body:
        try:
            return json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def _campus(request):
    return resolve_campus(request.user, request)


def _aware(value):
    if value is not None and timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _distribution(request, pk) -> Distribution:
    campus = _campus(request)
    queryset = Distribution.objects.filter(pk=pk)
    if campus is not None and not request.user.is_superuser:
        queryset = queryset.filter(campus=campus)
    distribution = queryset.select_related("campus").first()
    if distribution is None:
        raise Http404("Distribuição não encontrada.")
    return distribution


def _serialize_student(student):
    if student is None:
        return None
    return {
        "id": student.pk,
        "name": student.full_name,
        "registrationNumber": student.registration_number,
        "className": student.class_group.name if student.class_group else None,
    }


def _serialize_delivery(delivery):
    if delivery is None:
        return None
    return {
        "id": delivery.pk,
        "type": delivery.delivery_type,
        "status": delivery.status,
        "deliveredAt": delivery.delivered_at.isoformat(),
    }


# ---------------------------------------------------------------------------
@require_POST
@api_operator_required
def distribution_create(request):
    campus = _campus(request)
    if campus is None:
        return JsonResponse(
            {"detail": "Usuário sem campus definido.", "code": "no_campus"}, status=400
        )

    data = _payload(request)
    service_date = parse_date(data.get("service_date", "") or "")
    start = _aware(parse_datetime(data.get("planned_start_at", "") or ""))
    end = _aware(parse_datetime(data.get("planned_end_at", "") or ""))
    meal_type = data.get("meal_type")

    if not (service_date and start and end and meal_type):
        return JsonResponse(
            {
                "detail": "Informe service_date, meal_type, planned_start_at e planned_end_at.",
                "code": "invalid_payload",
            },
            status=400,
        )

    distribution = services.create_distribution(
        campus=campus,
        user=request.user,
        service_date=service_date,
        meal_type=meal_type,
        planned_start_at=start,
        planned_end_at=end,
        estimated_quantity=data.get("estimated_quantity") or None,
    )
    return JsonResponse(
        {"id": distribution.pk, "status": distribution.status}, status=201
    )


@require_POST
@api_operator_required
def distribution_open(request, pk):
    distribution = _distribution(request, pk)
    try:
        services.open_distribution(distribution=distribution, user=request.user)
    except DistributionStateError as exc:
        return JsonResponse({"detail": str(exc), "code": "invalid_state"}, status=409)
    except IntegrityError:
        return JsonResponse(
            {"detail": "Já existe uma distribuição aberta para este campus/data/refeição.",
             "code": "already_open"},
            status=409,
        )
    return JsonResponse({"id": distribution.pk, "status": distribution.status})


@require_POST
@api_operator_required
def distribution_close(request, pk):
    distribution = _distribution(request, pk)
    try:
        services.close_distribution(distribution=distribution, user=request.user)
    except DistributionStateError as exc:
        return JsonResponse({"detail": str(exc), "code": "invalid_state"}, status=409)
    return JsonResponse({"id": distribution.pk, "status": distribution.status})


@require_POST
@api_operator_required
def distribution_scan(request, pk):
    distribution = _distribution(request, pk)
    data = _payload(request)
    result = services.record_scan(
        distribution=distribution, token=data.get("token", ""), user=request.user
    )
    return JsonResponse(
        {
            "result": result.result,
            "student": _serialize_student(result.student),
            "delivery": _serialize_delivery(result.delivery),
            "previousDelivery": _serialize_delivery(result.previous_delivery),
            "message": result.message,
        }
    )


@require_POST
@api_authorize_required
def distribution_extras(request, pk):
    distribution = _distribution(request, pk)
    data = _payload(request)
    student = (
        Student.objects.filter(
            campus_id=distribution.campus_id,
            qr_token_hash=hash_token(data.get("token", "") or ""),
        )
        .select_related("class_group")
        .first()
    )
    if student is None:
        return JsonResponse(
            {"detail": "QR não reconhecido.", "code": "invalid_token"}, status=400
        )
    try:
        delivery = services.register_extra(
            distribution=distribution,
            student=student,
            reason=data.get("reason", ""),
            recorded_by=request.user,
            authorized_by=request.user,
        )
    except DistributionStateError as exc:
        return JsonResponse({"detail": str(exc), "code": "invalid_state"}, status=409)

    return JsonResponse(
        {
            "result": "EXTRA_DELIVERED",
            "student": _serialize_student(student),
            "delivery": _serialize_delivery(delivery),
            "message": "Entrega excedente registrada.",
        }
    )


@require_POST
@api_reverse_required
def delivery_reverse(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    data = _payload(request)
    try:
        services.reverse_delivery(
            delivery=delivery, reason=data.get("reason", ""), user=request.user
        )
    except DistributionStateError as exc:
        return JsonResponse({"detail": str(exc), "code": "invalid_state"}, status=409)
    return JsonResponse({"id": delivery.pk, "status": delivery.status})


@require_GET
@api_login_required
def distribution_summary(request, pk):
    distribution = _distribution(request, pk)
    return JsonResponse(services.distribution_summary(distribution))


@require_GET
@api_login_required
def distribution_pending(request, pk):
    distribution = _distribution(request, pk)
    students = services.pending_students(distribution)
    return JsonResponse(
        {
            "count": students.count(),
            "students": [
                {
                    "id": student.pk,
                    "name": student.full_name,
                    "registrationNumber": student.registration_number,
                    "className": student.class_group.name if student.class_group else None,
                }
                for student in students[:500]
            ],
        }
    )


@require_GET
@api_login_required
def distribution_report(request, pk):
    distribution = _distribution(request, pk)

    if request.GET.get("format") == "csv":
        buffer = io.StringIO()
        fieldnames = [
            "matricula", "nome", "turma", "tipo", "situacao", "entregue_em",
            "registrado_por", "autorizado_por", "motivo", "estornado_por", "motivo_estorno",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(services.report_rows(distribution))
        return HttpResponse(
            buffer.getvalue(),
            content_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="relatorio-{distribution.pk}.csv"'
            },
        )

    report = services.distribution_report(distribution)
    return JsonResponse(
        {
            "summary": report["summary"],
            "byClass": report["by_class"],
            "counts": {
                "regular": report["regular"].count(),
                "extras": report["extras"].count(),
                "reversed": report["reversed_deliveries"].count(),
            },
        }
    )
