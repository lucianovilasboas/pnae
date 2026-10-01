"""Serviços de importação de estudantes (CSV/XLSX) com prévia e aplicação.

Fluxo em duas fases: `create_import_preview` valida e guarda o arquivo, sem
alterar a base; `apply_import` relê o arquivo guardado e faz upsert dentro de
uma transação. Ver docs/03-api.md §8.
"""

import csv
import io

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from apps.audit.services import record_event

from .importers import parse_roster
from .models import ImportJob, ImportJobStatus, Student


def _write_error_report(job: ImportJob, errors) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["linha", "matricula", "motivo"])
    for error in errors:
        writer.writerow([error.line, error.registration_number, error.reason])
    path = default_storage.save(
        f"imports/{job.pk}/erros.csv",
        ContentFile(buffer.getvalue().encode("utf-8")),
    )
    return path


def create_import_preview(*, campus, user, uploaded_file):
    """Cria um ImportJob em PREVIEW. Não grava estudantes."""
    job = ImportJob.objects.create(
        campus=campus,
        created_by=user,
        file_name=uploaded_file.name,
        source_file=uploaded_file,
        status=ImportJobStatus.VALIDATING,
    )

    valid, errors, total = parse_roster(job.source_file, job.file_name, campus)

    job.total_rows = total
    job.rejected_rows = len(errors)
    job.status = ImportJobStatus.PREVIEW
    if errors:
        job.error_report_path = _write_error_report(job, errors)
    job.save(
        update_fields=["total_rows", "rejected_rows", "status", "error_report_path"]
    )

    record_event(
        action="students.import.preview",
        entity_type="ImportJob",
        entity_id=job.pk,
        actor=user,
        campus=campus,
        metadata={"total": total, "valid": len(valid), "rejected": len(errors)},
    )
    return job, valid, errors


@transaction.atomic
def apply_import(*, job: ImportJob, user):
    """Aplica a prévia: upsert dos estudantes válidos. Idempotente por matrícula."""
    if job.status != ImportJobStatus.PREVIEW:
        raise ValueError("Importação não está em prévia.")

    job.source_file.open("rb")
    valid, _errors, _total = parse_roster(job.source_file, job.file_name, job.campus)

    imported = 0
    for row in valid:
        Student.objects.update_or_create(
            campus=job.campus,
            registration_number=row.registration_number,
            defaults={
                "full_name": row.full_name,
                "email": row.email or "",
                "class_group": row.class_group,
                "active": True,
            },
        )
        imported += 1

    job.imported_rows = imported
    job.status = ImportJobStatus.APPLIED
    job.save(update_fields=["imported_rows", "status"])

    record_event(
        action="students.import.applied",
        entity_type="ImportJob",
        entity_id=job.pk,
        actor=user,
        campus=job.campus,
        metadata={"imported": imported, "rejected": job.rejected_rows},
    )
    return job
