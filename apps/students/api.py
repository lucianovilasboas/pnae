"""Endpoints JSON de estudantes: importação e exportação de QR.

Ver docs/03-api.md §8 e §2. Autorização: apenas administrador.
"""

import csv
import io

from django.core.files.storage import default_storage
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.decorators import api_admin_required
from apps.audit.services import record_event
from apps.campus.models import ClassGroup
from apps.campus.selectors import resolve_campus

from .importers import RosterFormatError
from .models import ImportJob, ImportJobStatus
from .qr import assign_tokens, qr_data_uri, students_for_qr
from .services import apply_import, create_import_preview


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
        "sample": [
            {
                "line": row.line,
                "registrationNumber": row.registration_number,
                "name": row.full_name,
                "className": row.class_group.name if row.class_group else None,
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


_QR_SHEET = """<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8">
<title>QR Codes — IFMG Alimenta</title>
<style>
  body {{ font-family: sans-serif; margin: 12px; }}
  .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
  .card {{ border: 1px solid #ccc; border-radius: 6px; padding: 8px; text-align: center;
           break-inside: avoid; }}
  .name {{ font-weight: bold; font-size: 13px; }}
  .meta {{ font-size: 11px; color: #444; }}
  img {{ width: 120px; height: 120px; }}
  @media print {{ .no-print {{ display: none; }} }}
</style></head><body>
<div class="no-print">
  <p>Atenção: esta exportação <strong>rotaciona</strong> os tokens dos {count} estudantes
  listados. QR Codes impressos antes deixam de valer.</p>
  <button onclick="window.print()">Imprimir</button>
</div>
<div class="grid">
{cards}
</div>
</body></html>"""


_CARD = """  <div class="card">
    <img src="{img}" alt="QR">
    <div class="name">{name}</div>
    <div class="meta">{registration}</div>
    <div class="meta">{class_name}</div>
  </div>"""


@require_POST
@api_admin_required
def qr_export(request):
    campus, error_response = _campus_or_400(request)
    if error_response:
        return error_response

    class_group = None
    class_group_id = request.POST.get("class_group")
    if class_group_id:
        class_group = get_object_or_404(ClassGroup, pk=class_group_id, campus=campus)

    only_missing = request.POST.get("only_missing") in {"1", "true", "on"}

    students = students_for_qr(campus, class_group=class_group, only_missing=only_missing)
    generated = assign_tokens(students)

    record_event(
        action="students.qr.exported",
        entity_type="Campus",
        entity_id=campus.pk,
        actor=request.user,
        campus=campus,
        metadata={"count": len(generated), "rotated": not only_missing},
    )

    cards = "\n".join(
        _CARD.format(
            img=qr_data_uri(token),
            name=escape(student.full_name),
            registration=escape(student.registration_number),
            class_name=escape(student.class_group.name if student.class_group else "—"),
        )
        for student, token in generated
    )
    html = _QR_SHEET.format(count=len(generated), cards=cards)
    return HttpResponse(html, content_type="text/html; charset=utf-8")
