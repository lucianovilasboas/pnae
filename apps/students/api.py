"""Endpoints JSON de estudantes: importação e exportação de QR.

Ver docs/03-api.md §8 e §2. Autorização: apenas administrador.
"""

import base64
import csv
import io
import os

from django.core.files.storage import default_storage
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.decorators import api_admin_required
from apps.audit.services import record_event
from apps.campus.models import ClassGroup
from apps.campus.selectors import resolve_campus

from .importers import RosterFormatError, missing_group_names
from .models import ImportJob, ImportJobStatus
from .qr import students_for_qr
from .services import apply_import, create_import_preview

_PAGE_SIZE = {"lista": 9, "carteirinha": 8}
_LOGO_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "svg": "image/svg+xml",
    "webp": "image/webp",
}


def _campus_or_400(request):
    campus = resolve_campus(request.user, request)
    if campus is None:
        return None, JsonResponse(
            {"detail": "Usuário sem campus definido.", "code": "no_campus"}, status=400
        )
    return campus, None


def _job_for_user(request, pk, campus):
    queryset = ImportJob.objects.filter(pk=pk)
    if not request.user.is_superuser:
        queryset = queryset.filter(campus=campus)
    job = queryset.first()
    if job is None:
        raise Http404("Importação não encontrada.")
    return job


def _serialize_preview(job, valid, errors):
    return {
        "id": job.pk,
        "status": job.status,
        "fileName": job.file_name,
        "totalRows": job.total_rows,
        "validRows": len(valid),
        "rejectedRows": job.rejected_rows,
        "newGroups": missing_group_names(job.campus, valid),
        "sample": [
            {
                "line": row.line,
                "registrationNumber": row.registration_number,
                "name": row.full_name,
                "className": row.class_group.label if row.class_group else None,
            }
            for row in valid[:50]
        ],
        "errors": [
            {
                "line": error.line,
                "registrationNumber": error.registration_number,
                "reason": error.reason,
            }
            for error in errors[:100]
        ],
    }


@require_POST
@api_admin_required
def import_create(request):
    campus, error_response = _campus_or_400(request)
    if error_response:
        return error_response

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return JsonResponse(
            {"detail": "Envie o arquivo no campo 'file'.", "code": "missing_file"},
            status=400,
        )

    try:
        job, valid, errors = create_import_preview(
            campus=campus, user=request.user, uploaded_file=uploaded
        )
    except RosterFormatError as exc:
        return JsonResponse({"detail": str(exc), "code": "invalid_roster"}, status=400)

    return JsonResponse(_serialize_preview(job, valid, errors), status=201)


@require_POST
@api_admin_required
def import_apply(request, pk):
    campus, error_response = _campus_or_400(request)
    if error_response:
        return error_response

    job = _job_for_user(request, pk, campus)
    if job.status != ImportJobStatus.PREVIEW:
        return JsonResponse(
            {"detail": "Importação não está em prévia.", "code": "not_preview"},
            status=409,
        )

    job = apply_import(job=job, user=request.user)
    return JsonResponse(
        {
            "id": job.pk,
            "status": job.status,
            "importedRows": job.imported_rows,
            "rejectedRows": job.rejected_rows,
        }
    )


@require_GET
@api_admin_required
def import_errors(request, pk):
    campus, error_response = _campus_or_400(request)
    if error_response:
        return error_response

    job = _job_for_user(request, pk, campus)
    if not job.error_report_path or not default_storage.exists(job.error_report_path):
        return HttpResponse(
            "linha;matricula;motivo\n",
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="erros-{job.pk}.csv"'},
        )

    with default_storage.open(job.error_report_path, "rb") as report:
        content = report.read()

    return HttpResponse(
        content,
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="erros-{job.pk}.csv"'},
    )


def _file_data_uri(field):
    """Lê um FileField e devolve data URI (funciona sem servir /media em prod)."""
    if not field:
        return None
    try:
        with field.open("rb") as handle:
            raw = handle.read()
    except (OSError, ValueError):
        return None
    ext = os.path.splitext(field.name)[1].lower().lstrip(".")
    mime = _LOGO_MIME.get(ext, "image/png")
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _chunk(items, size):
    for index in range(0, len(items), size):
        yield items[index : index + size]


@require_POST
@api_admin_required
def qr_export(request):
    campus, error_response = _campus_or_400(request)
    if error_response:
        return error_response

    layout = request.POST.get("layout", "lista")
    if layout not in _PAGE_SIZE:
        layout = "lista"

    class_group = None
    class_group_id = request.POST.get("class_group")
    if class_group_id:
        class_group = get_object_or_404(ClassGroup, pk=class_group_id, campus=campus)

    student_ids = [sid for sid in request.POST.getlist("students") if sid]
    if student_ids:
        class_group = None  # seleção explícita tem prioridade
    students = students_for_qr(campus, class_group=class_group, students=student_ids or None)

    record_event(
        action="students.qr.exported",
        entity_type="Campus",
        entity_id=campus.pk,
        actor=request.user,
        campus=campus,
        metadata={"count": len(students), "layout": layout},
    )

    template = "students/qr_badge.html" if layout == "carteirinha" else "students/qr_sheet.html"
    html = render_to_string(
        template,
        {
            "campus": campus,
            "students": students,
            "pages": list(_chunk(students, _PAGE_SIZE[layout])),
            "count": len(students),
            "logo": _file_data_uri(campus.logo),
            "generated_at": timezone.now(),
        },
        request=request,
    )
    return HttpResponse(html, content_type="text/html; charset=utf-8")
