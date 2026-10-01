from django.db import models


class Campus(models.Model):
    name = models.CharField("nome", max_length=150)
    code = models.CharField("código", max_length=30, unique=True)
    timezone = models.CharField("fuso horário", max_length=64, default="America/Sao_Paulo")
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
    name = models.CharField("turma", max_length=120)
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

    def __str__(self):
        return f"{self.name} — {self.academic_year}"
