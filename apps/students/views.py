"""Páginas (não-API) de estudantes: importar e exportar QR.

Mantidas simples e server-rendered; a versão com HTMX/feedback fino entra na
fase de telas. Autorização: administrador.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import is_admin
from apps.audit.services import record_event
from apps.campus.models import ClassGroup
from apps.campus.selectors import resolve_campus

from .importers import RosterFormatError, missing_group_names
from .models import ImportJob, ImportJobStatus, Student
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


STUDENTS_CRUMBS = [
    {"label": "Início", "url": "/"},
    {"label": "Estudantes"},
]


def _student_form_context(request, campus, student=None):
    groups = ClassGroup.objects.none()
    if campus is not None:
        groups = ClassGroup.objects.filter(campus=campus, active=True).order_by("name")
    breadcrumbs = [
        {"label": "Início", "url": "/"},
        {"label": "Estudantes", "url": "/estudantes/"},
        {"label": "Editar" if student else "Novo"},
    ]
    return {"class_groups": groups, "campus": campus, "student": student, "breadcrumbs": breadcrumbs}


def _student_payload(request, campus):
    group = None
    group_id = request.POST.get("class_group")
    if group_id:
        group = ClassGroup.objects.filter(pk=group_id, campus=campus).first()
    return {
        "registration_number": (request.POST.get("registration_number") or "").strip(),
        "full_name": (request.POST.get("full_name") or "").strip(),
        "email": (request.POST.get("email") or "").strip(),
        "course": (request.POST.get("course") or "").strip(),
        "class_group": group,
        "active": request.POST.get("active", "0") in {"1", "true", "on"},
    }


def _student_error(payload):
    if not payload["registration_number"]:
        return "Informe a matrícula."
    if not payload["full_name"]:
        return "Informe o nome do estudante."
    return None


@login_required
def student_list(request):
    denied = _require_admin(request)
    if denied:
        return denied

    campus = resolve_campus(request.user, request)
    queryset = Student.objects.none()
    if campus is not None:
        queryset = Student.objects.filter(campus=campus).select_related("class_group")

    busca = (request.GET.get("busca") or "").strip()
    if busca:
        queryset = queryset.filter(
            Q(full_name__icontains=busca)
            | Q(registration_number__icontains=busca)
            | Q(class_group__name__icontains=busca)
            | Q(class_group__display_name__icontains=busca)
        )

    status = request.GET.get("status", "ativos")
    if status == "ativos":
        queryset = queryset.filter(active=True)
    elif status == "inativos":
        queryset = queryset.filter(active=False)
    queryset = queryset.order_by("full_name")

    paginator = Paginator(queryset, 30)
    page = paginator.get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)

    return render(
        request,
        "students/list.html",
        {
            "students": page.object_list,
            "page": page,
            "querystring": query.urlencode(),
            "campus": campus,
            "busca": busca,
            "status": status,
            "breadcrumbs": list(STUDENTS_CRUMBS),
        },
    )


@login_required
def student_create(request):
    denied = _require_admin(request)
    if denied:
        return denied

    campus = resolve_campus(request.user, request)
    if request.method == "POST":
        if campus is None:
            messages.error(request, "Campus não definido.")
        else:
            payload = _student_payload(request, campus)
            error = _student_error(payload)
            if error:
                messages.error(request, error)
            else:
                try:
                    with transaction.atomic():
                        student = Student.objects.create(campus=campus, **payload)
                except IntegrityError:
                    messages.error(
                        request, "Já existe um estudante com esta matrícula neste campus."
                    )
                else:
                    record_event(
                        action="student.created",
                        entity_type="Student",
                        entity_id=student.pk,
                        actor=request.user,
                        campus=campus,
                        metadata={"registrationNumber": student.registration_number},
                    )
                    messages.success(request, "Estudante cadastrado.")
                    return redirect("students_pages:student-list")
    return render(request, "students/form.html", _student_form_context(request, campus))


@login_required
def student_edit(request, pk):
    denied = _require_admin(request)
    if denied:
        return denied

    campus = resolve_campus(request.user, request)
    student = get_object_or_404(Student, pk=pk)
    if campus is not None and student.campus_id != campus.pk and not request.user.is_superuser:
        messages.error(request, "Estudante de outro campus.")
        return redirect("students_pages:student-list")

    if request.method == "POST":
        payload = _student_payload(request, student.campus)
        error = _student_error(payload)
        if error:
            messages.error(request, error)
        else:
            for key, value in payload.items():
                setattr(student, key, value)
            try:
                with transaction.atomic():
                    student.save()
            except IntegrityError:
                messages.error(
                    request, "Já existe um estudante com esta matrícula neste campus."
                )
            else:
                record_event(
                    action="student.updated",
                    entity_type="Student",
                    entity_id=student.pk,
                    actor=request.user,
                    campus=student.campus,
                    metadata={"fields": sorted(payload.keys())},
                )
                messages.success(request, "Estudante atualizado.")
                return redirect("students_pages:student-list")

    return render(
        request, "students/form.html", _student_form_context(request, campus, student)
    )


@login_required
def student_deactivate(request, pk):
    denied = _require_admin(request)
    if denied:
        return denied
    if request.method != "POST":
        return redirect("students_pages:student-list")

    campus = resolve_campus(request.user, request)
    student = get_object_or_404(Student, pk=pk)
    if campus is not None and student.campus_id != campus.pk and not request.user.is_superuser:
        messages.error(request, "Estudante de outro campus.")
        return redirect("students_pages:student-list")

    if not student.active:
        messages.info(request, "Estudante já está inativo.")
    else:
        student.active = False
        student.save(update_fields=["active", "updated_at"])
        record_event(
            action="student.deactivated",
            entity_type="Student",
            entity_id=student.pk,
            actor=request.user,
            campus=student.campus,
            metadata={"registrationNumber": student.registration_number},
        )
        messages.success(request, "Estudante inativado.")
    return redirect("students_pages:student-list")
