"""Páginas de distribuição: painel, cadastro, operação, entregas e relatório."""

import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date, parse_datetime

from apps.accounts.decorators import can_reverse, is_operator
from apps.campus.models import ClassGroup
from apps.campus.selectors import resolve_campus

from . import services
from .models import Delivery, Distribution, DistributionStatus
from .services import DistributionStateError


def _require_operator(request):
    if not is_operator(request.user):
        return HttpResponseForbidden("Apenas operadores e administradores.")
    return None


def _scoped_distributions(request):
    campus = resolve_campus(request.user, request)
    queryset = Distribution.objects.all()
    if campus is not None and not request.user.is_superuser:
        queryset = queryset.filter(campus=campus)
    return campus, queryset.select_related("campus", "menu")


@login_required
def home(request):
    campus = resolve_campus(request.user, request)

    current = Distribution.objects.filter(status=DistributionStatus.OPEN)
    if campus is not None:
        current = current.filter(campus=campus)
    current = current.order_by("-opened_at").first()

    context = {"current_distribution": current, "summary": None}
    if current is not None:
        context["summary"] = services.distribution_summary(current)
    return render(request, "home.html", context)


@login_required
def distribution_list(request):
    denied = _require_operator(request)
    if denied:
        return denied

    campus, queryset = _scoped_distributions(request)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            _handle_create(request, campus)
        elif action in {"open", "close"}:
            _handle_transition(request, action, campus)
        return redirect("distributions:list")

    return render(
        request,
        "distributions/list.html",
        {"distributions": queryset.order_by("-service_date", "-id")[:50], "campus": campus},
    )


def _handle_create(request, campus):
    if campus is None:
        messages.error(request, "Campus não definido.")
        return
    service_date = parse_date(request.POST.get("service_date", "") or "")
    start = parse_datetime(request.POST.get("planned_start_at", "") or "")
    end = parse_datetime(request.POST.get("planned_end_at", "") or "")
    meal_type = request.POST.get("meal_type")
    if not (service_date and start and end and meal_type):
        messages.error(request, "Preencha data, refeição, início e fim.")
        return
    services.create_distribution(
        campus=campus,
        user=request.user,
        service_date=service_date,
        meal_type=meal_type,
        planned_start_at=start,
        planned_end_at=end,
    )
    messages.success(request, "Distribuição criada (rascunho).")


def _handle_transition(request, action, campus):
    distribution = get_object_or_404(Distribution, pk=request.POST.get("id"))
    if campus is not None and distribution.campus_id != campus.pk and not request.user.is_superuser:
        messages.error(request, "Distribuição de outro campus.")
        return
    try:
        if action == "open":
            services.open_distribution(distribution=distribution, user=request.user)
            messages.success(request, "Distribuição aberta.")
        else:
            services.close_distribution(distribution=distribution, user=request.user)
            messages.success(request, "Distribuição encerrada.")
    except DistributionStateError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "Não foi possível abrir: já existe distribuição aberta.")


@login_required
def operation(request, pk):
    denied = _require_operator(request)
    if denied:
        return denied

    _campus, queryset = _scoped_distributions(request)
    distribution = get_object_or_404(queryset, pk=pk)
    summary = services.distribution_summary(distribution)
    return render(
        request,
        "distributions/operation.html",
        {"distribution": distribution, "summary": summary},
    )


@login_required
def pending(request, pk):
    denied = _require_operator(request)
    if denied:
        return denied

    _campus, queryset = _scoped_distributions(request)
    distribution = get_object_or_404(queryset, pk=pk)

    class_group = None
    group_id = request.GET.get("turma")
    if group_id:
        class_group = ClassGroup.objects.filter(pk=group_id, campus=distribution.campus).first()

    students = services.pending_students(distribution, class_group=class_group)
    groups = ClassGroup.objects.filter(campus=distribution.campus, active=True).order_by("name")
    return render(
        request,
        "distributions/pending.html",
        {
            "distribution": distribution,
            "students": students,
            "groups": groups,
            "selected_group": class_group,
        },
    )


@login_required
def deliveries(request, pk):
    denied = _require_operator(request)
    if denied:
        return denied

    _campus, queryset = _scoped_distributions(request)
    distribution = get_object_or_404(queryset, pk=pk)

    if request.method == "POST" and request.POST.get("action") == "reverse":
        if not can_reverse(request.user):
            messages.error(request, "Você não tem permissão para estornar.")
        else:
            delivery = get_object_or_404(Delivery, pk=request.POST.get("delivery_id"))
            try:
                services.reverse_delivery(
                    delivery=delivery, reason=request.POST.get("reason", ""), user=request.user
                )
                messages.success(request, "Entrega estornada (registro original preservado).")
            except DistributionStateError as exc:
                messages.error(request, str(exc))
        return redirect("distributions:deliveries", pk=distribution.pk)

    items = (
        Delivery.objects.filter(distribution=distribution)
        .select_related("student", "student__class_group", "recorded_by", "authorized_by", "reversed_by")
        .order_by("-delivered_at")
    )
    return render(
        request,
        "distributions/deliveries.html",
        {"distribution": distribution, "deliveries": items, "can_reverse": can_reverse(request.user)},
    )


@login_required
def report(request, pk):
    denied = _require_operator(request)
    if denied:
        return denied

    _campus, queryset = _scoped_distributions(request)
    distribution = get_object_or_404(queryset, pk=pk)
    data = services.distribution_report(distribution)
    return render(request, "distributions/report.html", {"distribution": distribution, **data})


@login_required
def report_csv(request, pk):
    denied = _require_operator(request)
    if denied:
        return denied

    _campus, queryset = _scoped_distributions(request)
    distribution = get_object_or_404(queryset, pk=pk)

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
        headers={"Content-Disposition": f'attachment; filename="relatorio-{distribution.pk}.csv"'},
    )
