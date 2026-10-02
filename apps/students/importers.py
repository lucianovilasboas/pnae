"""Leitura e validação de planilhas de estudantes (CSV/XLSX).

Separa a leitura (formato) da validação (regras), para ser testável sem HTTP.
Regras mínimas: matrícula e nome obrigatórios; turma, quando informada, precisa
existir no campus; matrícula não pode repetir dentro do arquivo.
"""

import csv
import io
import unicodedata
from dataclasses import dataclass

from openpyxl import load_workbook

from apps.campus.models import ClassGroup

# Sinônimos aceitos para cada campo canônico (comparados já normalizados).
COLUMN_ALIASES = {
    "registration_number": {"matricula", "registration_number", "registration", "codigo"},
    "full_name": {"nome", "nome completo", "full_name", "name"},
    "email": {"email", "e-mail"},
    "class_group": {"turma", "class_group", "classe", "grupo"},
    "course": {"curso", "descricao do curso", "course"},
    "active": {"situacao no curso", "situacao", "status", "situacao do aluno"},
}

REQUIRED_FIELDS = ("registration_number", "full_name")

# Situações que mantêm o estudante ativo. Qualquer outra situação preenchida
# resulta em estudante inativo.
ACTIVE_STATUSES = {"matriculado", "ativo", "cursando", "regularmente matriculado"}


@dataclass
class ParsedRow:
    line: int
    registration_number: str
    full_name: str
    email: str
    class_group: ClassGroup | None = None
    class_group_name: str = ""
    course: str = ""
    active: bool = True


@dataclass
class RowError:
    line: int
    registration_number: str
    reason: str


class RosterFormatError(ValueError):
    """Arquivo ilegível ou sem as colunas obrigatórias."""


def _normalize(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def _map_columns(headers) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, header in enumerate(headers):
        normalized = _normalize(header)
        for field, aliases in COLUMN_ALIASES.items():
            if normalized in aliases and field not in mapping:
                mapping[field] = index
    missing = [field for field in REQUIRED_FIELDS if field not in mapping]
    if missing:
        raise RosterFormatError(
            "Colunas obrigatórias ausentes: " + ", ".join(missing) + "."
        )
    return mapping


def _rows_from_csv(data: bytes) -> list[list]:
    text = data.decode("utf-8-sig", errors="replace")
    if not text.strip():
        return []
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect)]


def _rows_from_xlsx(data: bytes) -> list[list]:
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet = workbook.active
    return [list(row) for row in sheet.iter_rows(values_only=True)]


def read_table(file_obj, filename: str) -> list[list]:
    data = file_obj.read()
    if isinstance(data, str):
        data = data.encode("utf-8")
    if filename.lower().endswith(".xlsx"):
        try:
            return _rows_from_xlsx(data)
        except Exception as exc:  # pragma: no cover - erro de arquivo corrompido
            raise RosterFormatError("Não foi possível ler o arquivo XLSX.") from exc
    if filename.lower().endswith(".csv"):
        return _rows_from_csv(data)
    raise RosterFormatError("Formato não suportado. Envie CSV ou XLSX.")


def parse_roster(
    file_obj,
    filename: str,
    campus,
    create_missing_groups: bool = True,
) -> tuple[list[ParsedRow], list[RowError], int]:
    """Devolve (linhas válidas, erros por linha, total de linhas de dados).

    Com `create_missing_groups=True`, uma turma informada que ainda não existe
    no campus é aceita (será criada na aplicação), carregando o nome da turma e
    o curso para criação. Caso contrário, é tratada como erro.
    """
    rows = read_table(file_obj, filename)
    if not rows:
        raise RosterFormatError("Arquivo vazio.")

    mapping = _map_columns(rows[0])
    groups = {_normalize(group.name): group for group in ClassGroup.objects.filter(campus=campus)}

    valid: list[ParsedRow] = []
    errors: list[RowError] = []
    seen_registrations: set[str] = set()
    total = 0

    for line_number, row in enumerate(rows[1:], start=2):
        def cell(field):
            index = mapping.get(field)
            if index is None or index >= len(row):
                return ""
            return str(row[index]).strip() if row[index] is not None else ""

        registration = cell("registration_number")
        full_name = cell("full_name")
        email = cell("email")
        group_name = cell("class_group")
        course = cell("course")
        status = cell("active")

        if not registration and not full_name:
            continue  # linha em branco
        total += 1

        if not registration:
            errors.append(RowError(line_number, "", "Matrícula ausente."))
            continue
        if not full_name:
            errors.append(RowError(line_number, registration, "Nome ausente."))
            continue
        if registration in seen_registrations:
            errors.append(RowError(line_number, registration, "Matrícula repetida no arquivo."))
            continue

        class_group = groups.get(_normalize(group_name)) if group_name else None
        if group_name and class_group is None and not create_missing_groups:
            errors.append(
                RowError(line_number, registration, f"Turma não encontrada: {group_name}.")
            )
            continue

        active = True
        if status:
            active = _normalize(status) in ACTIVE_STATUSES

        valid.append(
            ParsedRow(
                line=line_number,
                registration_number=registration,
                full_name=full_name,
                email=email,
                class_group=class_group,
                class_group_name=group_name,
                course=course,
                active=active,
            )
        )
        seen_registrations.add(registration)

    return valid, errors, total


def missing_group_names(campus, rows) -> list[str]:
    """Nomes de turmas que ainda não existem no campus (serão criadas)."""
    names = {row.class_group_name for row in rows if row.class_group_name and row.class_group is None}
    if not names:
        return []
    existing = set(
        ClassGroup.objects.filter(campus=campus, name__in=names).values_list("name", flat=True)
    )
    return sorted(names - existing)
