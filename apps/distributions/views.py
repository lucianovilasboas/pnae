"""Páginas de distribuição: painel, cadastro, operação, entregas e relatório."""

import csv
import io
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.decorators import can_reverse, is_operator
from apps.campus.models import ClassGroup
from apps.campus.selectors import resolve_campus
from apps.dates import WEEKDAY_LABELS, parse_weekdays
from apps.menus.models import MealType, Menu
from apps.menus.services import create_menus_bulk, plan_menus_bulk

from . import services
from .models import Delivery, Distribution, DistributionStatus
from .reasons import EXTRA_REASONS, REVERSAL_REASONS
from .services import DistributionStateError


def _require_operator(request):
    if not is_operator(request.user):
        return HttpResponseForbidden("Apenas operadores e administradores.")
    return None


def _scoped_distributions(request):
    campus = resolve_campus(request.user, request)
    # Auto-encerramento preguiçoso: distribuições abertas de dias anteriores.
    services.close_stale_distributions(campus=campus)
    queryset = Distribution.objects.all()
    if campus is not None and not request.user.is_superuser:
        queryset = queryset.filter(campus=campus)
    return campus, queryset.select_related("campus", "menu")


def _combine(service_date, hhmm):
    """Combina a data do serviço com um horário ``HH:MM`` no fuso corrente (RN-10).

    O formulário pede apenas o horário (a data já vem do campo Data); aqui as
    duas partes viram um ``datetime`` consciente de fuso.
    """
    if not service_date or not hhmm:
        return None
    try:
        parsed = datetime.strptime(hhmm, "%H:%M").time()
    except (TypeError, ValueError):
        return None
    return timezone.make_aware(
        datetime.combine(service_date, parsed), timezone.get_current_timezone()
    )


@login_required
def home(request):
    campus = resolve_campus(request.user, request)
    services.close_stale_distributions(campus=campus)

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
        elif action in {"open", "close", "reopen"}:
            _handle_transition(request, action, campus)
        elif action == "delete":
            _handle_delete(request, campus)
        elif action == "cancel":
            _handle_cancel(request, campus)
        return redirect("distributions:list")

    # Filtros e paginação.
    de = parse_date(request.GET.get("de", "") or "")
    ate = parse_date(request.GET.get("ate", "") or "")
    status = request.GET.get("status", "").strip()
    escopo = request.GET.get("escopo", "futuras")

    filtered = queryset
    if de:
        filtered = filtered.filter(service_date__gte=de)
    if ate:
        filtered = filtered.filter(service_date__lte=ate)
    if status:
        filtered = filtered.filter(status=status)
    if escopo == "futuras" and not de and not ate:
        filtered = filtered.filter(service_date__gte=timezone.localdate())
    filtered = filtered.order_by("service_date", "planned_start_at")

    paginator = Paginator(filtered, 20)
    page = paginator.get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)

    # Pré-preenchimento do formulário "Nova distribuição" ao voltar da aba de
    # Cardápios (data/refeição na querystring). Pré-seleciona o cardápio do dia,
    # se houver, para o operador só confirmar.
    pre_date = parse_date(request.GET.get("data", "") or "")
    pre_meal = request.GET.get("refeicao", "").strip()
    pre_menu = None
    if campus and pre_date and pre_meal:
        pre_menu = Menu.objects.filter(
            campus=campus, service_date=pre_date, meal_type=pre_meal
        ).first()
    form = {
        "service_date": request.GET.get("data", ""),
        "meal_type": pre_meal or MealType.SNACK,
        "inicio": "",
        "fim": "",
        "menu": pre_menu.pk if pre_menu else "",
    }
    return render(
        request,
        "distributions/list.html",
        {
            "distributions": page.object_list,
            "page": page,
            "querystring": query.urlencode(),
            "campus": campus,
            "form": form,
            "breadcrumbs": [
                {"label": "Início", "url": "/"},
                {"label": "Distribuições"},
            ],
            "menus": Menu.objects.filter(campus=campus).order_by("-service_date")[:30]
            if campus
            else Menu.objects.none(),
            "meal_types": MealType.choices,
            "status_choices": DistributionStatus.choices,
            "filters": {
                "de": request.GET.get("de", ""),
                "ate": request.GET.get("ate", ""),
                "status": status,
                "escopo": escopo,
            },
        },
    )


def _handle_create(request, campus):
    if campus is None:
        messages.error(request, "Campus não definido.")
        return
    service_date = parse_date(request.POST.get("service_date", "") or "")
    start = _combine(service_date, request.POST.get("inicio", ""))
    end = _combine(service_date, request.POST.get("fim", ""))
    meal_type = request.POST.get("meal_type") or MealType.SNACK
    menu = None
    menu_id = request.POST.get("menu")
    if menu_id:
        menu = Menu.objects.filter(pk=menu_id, campus=campus).first()
    if not (service_date and start and end and meal_type):
        messages.error(request, "Preencha data, refeição, início e fim.")
        return
    if end <= start:
        messages.error(request, "O fim previsto deve ser depois do início previsto.")
        return
    services.create_distribution(
        campus=campus,
        user=request.user,
        service_date=service_date,
        meal_type=meal_type,
        planned_start_at=start,
        planned_end_at=end,
        menu=menu,
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
        elif action == "reopen":
            services.reopen_distribution(distribution=distribution, user=request.user)
            messages.success(request, "Distribuição reaberta.")
        else:
            services.close_distribution(distribution=distribution, user=request.user)
            messages.success(request, "Distribuição encerrada.")
    except DistributionStateError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "Não foi possível abrir: já existe distribuição aberta.")


def _distribution_crumbs(distribution, current_label=None):
    """Migalhas: Início › Distribuições › <data — refeição> [› <tela>]."""
    label = f"{distribution.service_date:%d/%m/%Y} — {distribution.get_meal_type_display()}"
    crumbs = [
        {"label": "Início", "url": "/"},
        {"label": "Distribuições", "url": "/distribuicoes/"},
        {"label": label, "url": f"/distribuicoes/{distribution.pk}/operar/"},
    ]
    if current_label:
        crumbs.append({"label": current_label})
    else:
        crumbs[-1].pop("url")
    return crumbs


def _get_scoped_distribution(request, campus):
    distribution = get_object_or_404(Distribution, pk=request.POST.get("id"))
    if campus is not None and distribution.campus_id != campus.pk and not request.user.is_superuser:
        return None
    return distribution


def _handle_delete(request, campus):
    distribution = _get_scoped_distribution(request, campus)
    if distribution is None:
        messages.error(request, "Distribuição de outro campus.")
        return
    try:
        services.delete_distribution(distribution=distribution, user=request.user)
        messages.success(request, "Distribuição excluída.")
    except DistributionStateError as exc:
        messages.error(request, str(exc))


def _handle_cancel(request, campus):
    distribution = _get_scoped_distribution(request, campus)
    if distribution is None:
        messages.error(request, "Distribuição de outro campus.")
        return
    try:
        services.cancel_distribution(
            distribution=distribution,
            user=request.user,
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "Distribuição cancelada.")
    except DistributionStateError as exc:
        messages.error(request, str(exc))


@login_required
def distribution_edit(request, pk):
    denied = _require_operator(request)
    if denied:
        return denied

    _campus, queryset = _scoped_distributions(request)
    distribution = get_object_or_404(queryset, pk=pk)
    if distribution.status != DistributionStatus.DRAFT:
        messages.error(request, "Só é possível editar uma distribuição em rascunho.")
        return redirect("distributions:list")

    if request.method == "POST":
        service_date = parse_date(request.POST.get("service_date", "") or "")
        start = _combine(service_date, request.POST.get("inicio", ""))
        end = _combine(service_date, request.POST.get("fim", ""))
        meal_type = request.POST.get("meal_type") or MealType.SNACK
        menu_id = request.POST.get("menu")
        menu = Menu.objects.filter(pk=menu_id, campus=distribution.campus).first() if menu_id else None
        estimated = request.POST.get("estimated_quantity") or None
        if not (service_date and start and end and meal_type and end > start):
            messages.error(request, "Preencha os campos e garanta que o fim seja após o início.")
        else:
            services.update_distribution(
                distribution=distribution,
                user=request.user,
                service_date=service_date,
                meal_type=meal_type,
                menu=menu,
                planned_start_at=start,
                planned_end_at=end,
                estimated_quantity=estimated,
            )
            messages.success(request, "Distribuição atualizada.")
            return redirect("distributions:list")

    menus = Menu.objects.filter(campus=distribution.campus).order_by("-service_date")[:30]
    return render(
        request,
        "distributions/edit.html",
        {
            "distribution": distribution,
            "menus": menus,
            "meal_types": MealType.choices,
            "breadcrumbs": _distribution_crumbs(distribution, "Editar"),
        },
    )


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
        {
            "distribution": distribution,
            "summary": summary,
            "extra_reasons": EXTRA_REASONS,
            "breadcrumbs": _distribution_crumbs(distribution),
        },
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
            "breadcrumbs": _distribution_crumbs(distribution, "Pendentes"),
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
        {
            "distribution": distribution,
            "deliveries": items,
            "can_reverse": can_reverse(request.user),
            "reversal_reasons": REVERSAL_REASONS,
            "breadcrumbs": _distribution_crumbs(distribution, "Entregas"),
        },
    )


@login_required
def report(request, pk):
    denied = _require_operator(request)
    if denied:
        return denied

    _campus, queryset = _scoped_distributions(request)
    distribution = get_object_or_404(queryset, pk=pk)
    data = services.distribution_report(distribution)
    return render(
        request,
        "distributions/report.html",
        {**data, "distribution": distribution, "breadcrumbs": _distribution_crumbs(distribution, "Relatório")},
    )


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


def _parse_time(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None


@login_required
def batch(request):
    """Criação em lote de distribuições e cardápios (período × dias da semana)."""
    denied = _require_operator(request)
    if denied:
        return denied

    campus = resolve_campus(request.user, request)
    context = {
        "campus": campus,
        "meal_types": MealType.choices,
        "weekdays": list(enumerate(WEEKDAY_LABELS)),
        "default_weekdays": [0, 1, 2, 3, 4],
        "selected_weekdays": {0, 1, 2, 3, 4},
        "form": {},
        "preview": None,
        "breadcrumbs": [
            {"label": "Início", "url": "/"},
            {"label": "Distribuições", "url": "/distribuicoes/"},
            {"label": "Criar em lote"},
        ],
    }

    if request.method == "POST":
        kind = request.POST.get("kind")  # "distributions" | "menus"
        action = request.POST.get("action")  # "preview" | "create"
        start = parse_date(request.POST.get("de", "") or "")
        end = parse_date(request.POST.get("ate", "") or "")
        weekdays = parse_weekdays(request.POST.getlist("weekdays"))
        meal_type = request.POST.get("meal_type") or MealType.SNACK

        context["form"] = {
            "kind": kind,
            "action": action,
            "de": request.POST.get("de", ""),
            "ate": request.POST.get("ate", ""),
            "weekdays": [str(d) for d in sorted(weekdays)],
            "meal_type": meal_type,
            "inicio": request.POST.get("inicio", ""),
            "fim": request.POST.get("fim", ""),
            "description": request.POST.get("description", ""),
            "notes": request.POST.get("notes", ""),
            "estimated_quantity": request.POST.get("estimated_quantity", ""),
        }
        context["selected_weekdays"] = weekdays or {0, 1, 2, 3, 4}

        if campus is None:
            messages.error(request, "Campus não definido.")
        elif start is None or end is None or end < start:
            messages.error(request, "Informe um período válido (data inicial ≤ data final).")
        elif not weekdays:
            messages.error(request, "Selecione pelo menos um dia da semana.")
        elif kind == "menus":
            description = (request.POST.get("description") or "").strip()
            if not description:
                messages.error(request, "Informe a descrição do cardápio.")
            else:
                to_create, existing = plan_menus_bulk(
                    campus=campus, start_date=start, end_date=end,
                    weekdays=weekdays, meal_type=meal_type,
                )
                if action == "create":
                    result = create_menus_bulk(
                        campus=campus, user=request.user, start_date=start, end_date=end,
                        weekdays=weekdays, meal_type=meal_type, description=description,
                        notes=(request.POST.get("notes") or "").strip(),
                    )
                    messages.success(
                        request,
                        f"Cardápios criados: {result['created']} (pulados {result['skipped']}).",
                    )
                    return redirect("menus:list")
                context["preview"] = {
                    "kind": "menus", "to_create": to_create, "existing": existing,
                    "meal_type": meal_type, "description": description,
                }
        else:  # distribuições
            start_time = _parse_time(request.POST.get("inicio", ""))
            end_time = _parse_time(request.POST.get("fim", ""))
            estimated = request.POST.get("estimated_quantity") or None
            if start_time is None or end_time is None or start_time >= end_time:
                messages.error(request, "Informe horários válidos (início antes do fim).")
            else:
                to_create, existing = services.plan_distributions_bulk(
                    campus=campus, start_date=start, end_date=end,
                    weekdays=weekdays, meal_type=meal_type,
                )
                if action == "create":
                    result = services.create_distributions_bulk(
                        campus=campus, user=request.user, start_date=start, end_date=end,
                        weekdays=weekdays, meal_type=meal_type, start_time=start_time,
                        end_time=end_time, estimated_quantity=estimated,
                    )
                    messages.success(
                        request,
                        f"Distribuições criadas: {result['created']} "
                        f"(puladas {result['skipped']}).",
                    )
                    return redirect("distributions:list")
                context["preview"] = {
                    "kind": "distributions", "to_create": to_create, "existing": existing,
                    "meal_type": meal_type, "start_time": start_time, "end_time": end_time,
                }

    return render(request, "distributions/batch.html", context)
