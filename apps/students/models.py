from django.db import models
from django.utils import timezone


def _current_year():
    return timezone.localdate().year


class ImportJobStatus(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    VALIDATING = "VALIDATING", "Validando"
    PREVIEW = "PREVIEW", "Prévia"
    APPLIED = "APPLIED", "Aplicada"
    FAILED = "FAILED", "Falhou"


class Student(models.Model):
    campus = models.ForeignKey(
        "campus.Campus", on_delete=models.PROTECT, related_name="students", verbose_name="campus"
    )
    registration_number = models.CharField("matrícula", max_length=40)
    full_name = models.CharField("nome completo", max_length=200)
    email = models.EmailField("e-mail", blank=True)
    cpf = models.CharField("CPF", max_length=20, blank=True)
    sexo = models.CharField("sexo", max_length=20, blank=True)
    course_code = models.CharField("código do curso", max_length=40, blank=True)
    course = models.CharField("curso", max_length=120, blank=True)
    situation_period = models.CharField("situação no período", max_length=60, blank=True)
    school_origin = models.CharField("tipo de escola de origem", max_length=60, blank=True)
    plan_row = models.CharField("linha da planilha", max_length=20, blank=True)
    class_group = models.ForeignKey(
        "campus.ClassGroup",
        on_delete=models.SET_NULL,
        related_name="students",
        verbose_name="turma",
        null=True,
        blank=True,
    )
    active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "estudante"
        verbose_name_plural = "estudantes"
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["campus", "registration_number"],
                name="uniq_student_campus_registration",
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.registration_number})"


class ImportJob(models.Model):
    campus = models.ForeignKey(
        "campus.Campus", on_delete=models.PROTECT, related_name="import_jobs", verbose_name="campus"
    )
    file_name = models.CharField("arquivo", max_length=255)
    source_file = models.FileField("arquivo enviado", upload_to="imports/%Y/%m/", blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="import_jobs", verbose_name="autor"
    )
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    academic_year = models.PositiveIntegerField("ano letivo", default=_current_year)
    status = models.CharField(
        "situação", max_length=20, choices=ImportJobStatus.choices, default=ImportJobStatus.PENDING
    )
    total_rows = models.PositiveIntegerField("linhas totais", default=0)
    imported_rows = models.PositiveIntegerField("linhas importadas", default=0)
    rejected_rows = models.PositiveIntegerField("linhas rejeitadas", default=0)
    error_report_path = models.CharField("relatório de erros", max_length=500, blank=True)

    class Meta:
        verbose_name = "importação"
        verbose_name_plural = "importações"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file_name} ({self.get_status_display()})"
