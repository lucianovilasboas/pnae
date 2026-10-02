"""Constraint único em Menu (campus, data, refeição).

Antes de criar o índice, remove eventuais duplicados existentes, mantendo o
registro mais recente (maior id) por (campus, service_date, meal_type).
"""

from django.db import migrations, models


def remove_duplicates(apps, schema_editor):
    Menu = apps.get_model("menus", "Menu")
    seen = set()
    to_delete = []
    for menu in Menu.objects.order_by("-id"):
        key = (menu.campus_id, menu.service_date, menu.meal_type)
        if key in seen:
            to_delete.append(menu.pk)
        else:
            seen.add(key)
    if to_delete:
        Menu.objects.filter(pk__in=to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("campus", "0002_classgroup_display_name_classgroup_source_code_and_more"),
        ("menus", "0002_alter_menu_meal_type"),
    ]

    operations = [
        migrations.RunPython(remove_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="menu",
            constraint=models.UniqueConstraint(
                fields=("campus", "service_date", "meal_type"),
                name="uniq_menu_campus_date_type",
            ),
        ),
    ]
