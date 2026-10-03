"""Views do portal do aluno (autenticação, cardápio e QR)."""

from datetime import timedelta

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.menus.models import Menu
from apps.students.qr import qr_data_uri

from .decorators import (
    get_current_account,
    login_account,
    logout_account,
    student_login_required,
)
from .services import PortalAuthError, authenticate, first_access, recover

ATTEMPT_LIMIT = 10
ATTEMPT_WINDOW = 300  # segundos


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _throttle_key(request, scope):
    return f"portal-throttle:{scope}:{_client_ip(request)}"


def _blocked(request, scope):
    return cache.get(_throttle_key(request, scope), 0) >= ATTEMPT_LIMIT


def _register_failure(request, scope):
    key = _throttle_key(request, scope)
    cache.set(key, cache.get(key, 0) + 1, ATTEMPT_WINDOW)


def _clear_failures(request, scope):
    cache.delete(_throttle_key(request, scope))


def home(request):
    if get_current_account(request):
        return redirect("portal:dashboard")
    return redirect("portal:login")


def login_view(request):
    if get_current_account(request):
        return redirect("portal:dashboard")
    if request.method == "POST":
        if _blocked(request, "login"):
            messages.error(request, "Muitas tentativas. Aguarde alguns minutos.")
            return render(request, "portal/login.html")
        account = authenticate(
            email=request.POST.get("email", ""), password=request.POST.get("password", "")
        )
        if account is None:
            _register_failure(request, "login")
            messages.error(request, "E-mail ou senha inválidos.")
        else:
            _clear_failures(request, "login")
            login_account(request, account)
            return redirect("portal:dashboard")
    return render(request, "portal/login.html")


def first_access_view(request):
    if request.method == "POST":
        if _blocked(request, "first"):
            messages.error(request, "Muitas tentativas. Aguarde alguns minutos.")
            return render(request, "portal/first_access.html")
        try:
            account = first_access(
                registration_number=request.POST.get("registration_number", ""),
                cpf=request.POST.get("cpf", ""),
                password=request.POST.get("password", ""),
                password2=request.POST.get("password2", ""),
            )
        except PortalAuthError as exc:
            _register_failure(request, "first")
            messages.error(request, str(exc))
        else:
            _clear_failures(request, "first")
            login_account(request, account)
            messages.success(request, "Conta criada. Bem-vindo(a)!")
            return redirect("portal:dashboard")
    return render(request, "portal/first_access.html")


def recover_view(request):
    if request.method == "POST":
        if _blocked(request, "recover"):
            messages.error(request, "Muitas tentativas. Aguarde alguns minutos.")
            return render(request, "portal/recover.html")
        try:
            recover(
                registration_number=request.POST.get("registration_number", ""),
                cpf=request.POST.get("cpf", ""),
                password=request.POST.get("password", ""),
                password2=request.POST.get("password2", ""),
            )
        except PortalAuthError as exc:
            _register_failure(request, "recover")
            messages.error(request, str(exc))
        else:
            _clear_failures(request, "recover")
            messages.success(request, "Senha redefinida. Faça login.")
            return redirect("portal:login")
    return render(request, "portal/recover.html")


@require_POST
def logout_view(request):
    logout_account(request)
    return redirect("portal:login")


# ---------------------------------------------------------------------------
# Cardápio e QR
# ---------------------------------------------------------------------------
def _published_menus(campus, start, end):
    return (
        Menu.objects.filter(
            campus=campus,
            published=True,
            service_date__gte=start,
            service_date__lte=end,
        )
        .order_by("service_date", "meal_type")
    )


def _start_of_week(day):
    return day - timedelta(days=day.weekday())


@student_login_required
def dashboard(request):
    student = request.portal_account.student
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    menus = list(_published_menus(student.campus, today, tomorrow))
    return render(
        request,
        "portal/dashboard.html",
        {
            "student": student,
            "today": today,
            "tomorrow": tomorrow,
            "today_menus": [m for m in menus if m.service_date == today],
            "tomorrow_menus": [m for m in menus if m.service_date == tomorrow],
        },
    )


@student_login_required
def week(request):
    student = request.portal_account.student
    today = timezone.localdate()
    start = _start_of_week(today)
    end = start + timedelta(days=6)
    by_date = {}
    for menu in _published_menus(student.campus, start, end):
        by_date.setdefault(menu.service_date, []).append(menu)
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        days.append({"date": day, "menus": by_date.get(day, [])})
    return render(
        request,
        "portal/week.html",
        {"student": student, "today": today, "days": days, "start": start, "end": end},
    )


@student_login_required
def qr_view(request):
    student = request.portal_account.student
    response = render(
        request,
        "portal/qr.html",
        {"student": student, "qr": qr_data_uri(student.registration_number)},
    )
    response["Cache-Control"] = "no-store"
    return response
