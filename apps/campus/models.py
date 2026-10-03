from django.db import models


class Campus(models.Model):
    name = models.CharField("nome", max_length=150)
    code = models.CharField("código", max_length=30, unique=True)
    timezone = models.CharField("fuso horário", max_length=64, default="America/Sao_Paulo")
    logo = models.ImageField("logo", upload_to="campus/", blank=True, null=True)
    active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "campus"
        verbose_name_plural = "campus"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class ClassGroup(models.Model):
    campus = models.ForeignKey(
        Campus, on_delete=models.PROTECT, related_name="class_groups", verbose_name="campus"
    )
    name = models.CharField("turma (código)", max_length=120)
    display_name = models.CharField("turma (exibição)", max_length=120, blank=True)
    source_code = models.CharField("código de origem", max_length=60, blank=True)
    course = models.CharField("curso", max_length=120, blank=True)
    academic_year = models.PositiveIntegerField("ano letivo")
    active = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "turma"
        verbose_name_plural = "turmas"
        ordering = ["campus", "academic_year", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["campus", "name", "academic_year"],
                name="uniq_classgroup_campus_name_year",
            )
        ]

    @property
    def label(self):
        return self.display_name or self.name

    def __str__(self):
        return f"{self.label} — {self.academic_year}"
