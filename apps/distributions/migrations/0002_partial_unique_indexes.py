"""Índices únicos parciais (regras inegociáveis, garantidas pelo banco).

- `uniq_delivery_regular_ativa`: no máximo uma entrega REGULAR/VALIDA por
  (distribuição, estudante). Protege contra leituras concorrentes (RN-03).
- `uniq_distribution_open`: no máximo uma distribuição ABERTA por
  (campus, data, refeição).

Ver docs/02-modelo-dados.md §4. PostgreSQL específico.
"""

from django.db import migrations

FORWARD_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS uniq_delivery_regular_ativa
    ON distributions_delivery (distribution_id, student_id)
    WHERE delivery_type = 'REGULAR' AND status = 'VALIDA';

CREATE UNIQUE INDEX IF NOT EXISTS uniq_distribution_open
    ON distributions_distribution (campus_id, service_date, meal_type)
    WHERE status = 'OPEN';
"""

REVERSE_SQL = """
DROP INDEX IF EXISTS uniq_delivery_regular_ativa;
DROP INDEX IF EXISTS uniq_distribution_open;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("distributions", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
