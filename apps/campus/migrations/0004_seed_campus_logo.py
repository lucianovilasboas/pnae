"""Semeia o logo do campus Ponte Nova (PN) a partir do arquivo estático.

Assim o cabeçalho impresso já sai com o logo do campus sem depender de upload
manual. Idempotente: só grava se o campus existir e ainda não tiver logo.
"""

import os

from django.conf import settings
from django.core.files import File
from django.db import migrations

SOURCE = "static/img/campus-ponte-nova.png"
TARGET_NAME = "campus-ponte-nova.png"


def seed_pn_logo(apps, schema_editor):
    Campus = apps.get_model("campus", "Campus")
    path = os.path.join(settings.BASE_DIR, SOURCE)
    if not os.path.exists(path):
        return
    campus = Campus.objects.filter(code="PN").first()
    if campus is None or campus.logo:
        return
    with open(path, "rb") as fh:
        campus.logo.save(TARGET_NAME, File(fh), save=True)


def unseed_pn_logo(apps, schema_editor):
    Campus = apps.get_model("campus", "Campus")
    campus = Campus.objects.filter(code="PN").first()
    if campus and campus.logo:
        campus.logo.delete(save=True)


class Migration(migrations.Migration):
    dependencies = [("campus", "0003_campus_logo")]

    operations = [migrations.RunPython(seed_pn_logo, unseed_pn_logo)]
