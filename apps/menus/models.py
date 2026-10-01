from django.db import models


class MealType(models.TextChoices):
    LUNCH = "LUNCH", "Almoço"
    DINNER = "DINNER", "Jantar"
    SNACK = "SNACK", "Lanche"
    OTHER = "OTHER", "Outro"


class Menu(models.Model):
    campus = models.ForeignKey(
        "campus.Campus", on_delete=models.PROTECT, related_name="menus", verbose_name="campus"
    )
    service_date = models.DateField("data do serviço")
    meal_type = models.CharField("refeição", max_length=20, choices=MealType.choices)
    description = models.TextField("descrição")
    notes = models.TextField("observações", blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="menus", verbose_name="autor"
    )
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "cardápio"
        verbose_name_plural = "cardápios"
        ordering = ["-service_date", "meal_type"]
        indexes = [
            models.Index(
                fields=["campus", "service_date", "meal_type"],
                name="idx_menu_campus_date_type",
            )
        ]

    def __str__(self):
        return f"{self.service_date} — {self.get_meal_type_display()}"
