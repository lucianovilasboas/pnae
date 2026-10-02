"""Páginas (não-API) de estudantes: importar e exportar QR.

Mantidas simples e server-rendered; a versão com HTMX/feedback fino entra na
fase de telas. Autorização: administrador.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import is_admin
from apps.campus.models import ClassGroup
from apps.campus.selectors import resolve_campus

from .importers import RosterFormatError, missing_group_names
from .models import ImportJob, ImportJobStatus
from .services import apply_import, create_import_preview


def _require_admin(request):
    if not is_admin(request.user):
        return HttpResponseForbidden("Apenas administradores.")
    return None


IMPORT_CRUMBS = [
    {"label": "Início", "url": "/"},
    {"label": "Estudantes"},
    {"label": "Importar"},
]
QR_CRUMBS = [
    {"label": "Início", "url": "/"},
    {"label": "Estudantes"},
    {"label": "QR Codes"},
]


@login_required
def import_page(request):
    denied = _require_admin(request)
    if denied:
        return denied

    if request.method == "POST":
        uploaded = request.FILES.get("file")
        campus = resolve_campus(request.user, request)
        if uploaded is None:
            messages.error(request, "Selecione um arquivo CSV ou XLSX.")
        elif campus is None:
            messages.error(request, "Defina o campus do usuário ou informe a qual campus importar.")
        else:
            try:
                job, valid, errors = create_import_preview(
                    campus=campus, user=request.user, uploaded_file=uploaded
                )
            except RosterFormatError as exc:
                messages.error(request, str(exc))
            else:
                return render(
                    request,
                    "students/import_preview.html",
                    {
                        "job": job,
                        "valid": valid[:50],
                        "valid_total": len(valid),
                        "errors": errors[:100],
                        "new_groups": missing_group_names(campus, valid),
                        "breadcrumbs": IMPORT_CRUMBS,
                    },
                )
        return render(request, "students/import.html", {"breadcrumbs": IMPORT_CRUMBS})

    return render(request, "students/import.html", {"breadcrumbs": IMPORT_CRUMBS})


@login_required
def import_confirm(request, pk):
    denied = _require_admin(request)
    if denied:
        return denied
    if request.method != "POST":
        return redirect("students_pages:import-page")

    campus = resolve_campus(request.user, request)
    if campus is None:
        messages.error(request, "Campus não definido.")
        return redirect("students_pages:import-page")

    job = get_object_or_404(ImportJob, pk=pk, campus=campus)
    if job.status != ImportJobStatus.PREVIEW:
        messages.error(request, "Importação não está em prévia.")
        return redirect("students_pages:import-page")

    job = apply_import(job=job, user=request.user)
    messages.success(
        request, f"{job.imported_rows} estudante(s) importado(s), {job.rejected_rows} rejeitado(s)."
    )
    return redirect("students_pages:import-page")


@login_required
def qr_page(request):
    denied = _require_admin(request)
    if denied:
        return denied

    campus = resolve_campus(request.user)
    groups = ClassGroup.objects.none()
    if campus is not None:
        groups = ClassGroup.objects.filter(campus=campus, active=True).order_by("name")
    return render(
        request,
        "students/qr.html",
        {"class_groups": groups, "campus": campus, "breadcrumbs": QR_CRUMBS},
    )
