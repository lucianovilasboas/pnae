# 02 — Modelo de dados

Tradução do §6 do [plano do MVP](../plano_mvp_ifmg_alimenta.md) para models
Django e constraints reais no PostgreSQL. **A constraint é a fonte de verdade**;
a aplicação não substitui o banco.

## 1. Convenções

- PK `BigAutoField` (`id`); `created_at`/`updated_at` quando aplicável.
- Dinheiro/quantidades: `IntegerField`/`PositiveIntegerField` para contagens.
- Horários: `DateTimeField` em **UTC** (`USE_TZ=True`), apresentados no fuso do
  campus (`Campus.timezone`). Datas de serviço: `DateField`.
- Enums como `TextChoices` (armazenados como texto curto).
- Exclusão lógica: `active`/`status`; **nunca** `DELETE` físico em entidades
  auditáveis (ver RN-09).

## 2. Diagrama textual

```
Campus 1─* ClassGroup 1─* Student
Campus 1─* User (nullable para admin global)
Campus 1─* Menu
Campus 1─* Distribution *─1 Menu (nullable)
Distribution 1─* Delivery *─1 Student
Delivery 1─0..1 Delivery (reverse: aponta para original? não — ver §6)
Campus 1─* AuditEvent
Campus 1─* ImportJob
```

## 3. Models

### Campus (`apps/campus`)
```text
id, name, code (unique), timezone (default "America/Sao_Paulo"), active
```

### ClassGroup (`apps/campus`)
```text
id, campus_id FK, name, course, academic_year, active
unique (campus_id, name, academic_year)
```

### Student (`apps/students`)
```text
id, campus_id FK, registration_number, full_name, email,
class_group_id FK (nullable), qr_token_hash, active,
created_at, updated_at
unique (campus_id, registration_number)
index  (qr_token_hash)          # busca da leitura
```
- `registration_number`, `full_name` são os únicos dados pessoais usados na
  operação; QR guarda **somente** `qr_token_hash`.
- `email` opcional no MVP.

### User (`apps/accounts`)
```text
id, campus_id FK null (admin global), name, email (unique),
role ∈ {ADMIN, OPERATOR, MANAGER},
can_authorize_extras (bool), can_reverse_deliveries (bool), active
```
- `AbstractBaseUser`/`PermissionsMixin` do Django como base; login por e-mail.

### Menu (`apps/menus`)
```text
id, campus_id FK, service_date, meal_type ∈ {SNACK, LUNCH, DINNER, OTHER} (padrão SNACK),
description, notes, created_by FK(User), created_at
index (campus_id, service_date, meal_type)
```

### Distribution (`apps/distributions`)
```text
id, campus_id FK, menu_id FK null, service_date,
meal_type ∈ {...}, planned_start_at, planned_end_at,
status ∈ {DRAFT, OPEN, CLOSED, CANCELED},
estimated_quantity null,
extras_enabled_at null, extras_enabled_by FK(User) null,
opened_by FK(User) null, closed_by FK(User) null,
opened_at null, closed_at null,
created_at, updated_at
index (campus_id, service_date, status)
```
- Máquina de estados: `DRAFT → OPEN → CLOSED`; `CANCELED` a partir de
  `DRAFT`/`OPEN`. Uma distribuição `CLOSED` **pode ser reaberta no mesmo dia**
  (registrando `distribution.reopened` na auditoria); fora do dia, criar nova
  sessão.
- Apenas uma `OPEN` por `(campus_id, service_date, meal_type)` — reforçar com
  índice único parcial (ver §4).

### Delivery (`apps/distributions`)
```text
id, distribution_id FK, student_id FK,
delivery_type ∈ {REGULAR, EXCEDENTE},
delivered_at, recorded_by FK(User),
authorized_by FK(User) null, reason null,
status ∈ {VALIDA, ESTORNADA},
reversed_at null, reversed_by FK(User) null, reversal_reason null,
created_at
index (distribution_id, student_id)
```
- `EXCEDENTE` exige `reason`, `recorded_by` e `authorized_by` não nulos
  (validação de aplicação + `CheckConstraint`).
- Estorno: **não apaga**; seta `status=ESTORNADA`, `reversed_at/by/reason`.

### AuditEvent (`apps/audit`)
```text
id, campus_id FK, actor_id FK(User) null, action,
entity_type, entity_id, occurred_at, metadata_json
index (campus_id, occurred_at), (entity_type, entity_id)
```
- `metadata_json` guarda apenas o necessário (sem token, sem dado pessoal
  excessivo).

### ImportJob (`apps/students`)
```text
id, campus_id FK, file_name, source_file (arquivo enviado, MEDIA),
created_by FK(User), created_at, academic_year,
status ∈ {PENDING, VALIDATING, PREVIEW, APPLIED, FAILED},
total_rows, imported_rows, rejected_rows, error_report_path null
```
- `source_file` guarda o arquivo para permitir a releitura no momento de
  aplicar a prévia (a validação não grava estudantes).
- `academic_year` é o ano letivo usado ao criar turmas novas a partir da
  coluna `Turma` do arquivo (default: ano corrente).
- `error_report_path` aponta para o CSV de linhas rejeitadas em MEDIA.
- A importação cria `ClassGroup` faltantes (nome = código da turma do arquivo,
  `course` = coluna de curso) e mapeia `Situação no Curso` → `Student.active`.

## 4. Constraints no PostgreSQL (obrigatórias)

Criadas em migrations `RunSQL`/`AddConstraint`, não só na interface:

1. `unique (campus_id, registration_number)` em `Student`.
2. índice em `Student.qr_token_hash`.
3. índice em `Delivery (distribution_id, student_id)`.
4. **índice único parcial** — a regra mais importante do MVP:
   ```sql
   CREATE UNIQUE INDEX uniq_regular_ativa
     ON distributions_delivery (distribution_id, student_id)
     WHERE delivery_type = 'REGULAR' AND status = 'VALIDA';
   ```
   Protege contra duas leituras concorrentes do mesmo QR. Excedente fica fora do
   índice (pode coexistir com a regular).
5. `CHECK (delivery_type IN ('REGULAR','EXCEDENTE'))` e
   `CHECK (status IN ('VALIDA','ESTORNADA'))`.
6. `CHECK` de excedente: `delivery_type <> 'EXCEDENTE' OR (reason IS NOT NULL
   AND authorized_by_id IS NOT NULL)`.
7. índice único parcial para uma única `Distribution` `OPEN` por
   `(campus_id, service_date, meal_type)`.

## 5. Token QR — decisão de hash

Necessidade: gerar token opaco de alta entropia, **buscar pelo hash** na leitura
e não guardar o token bruto (RN-07 / LGPD).

- **Escolha:** `qr_token_hash = HMAC-SHA256(pepper_secret, token)` em
  hexadecimal/Base64 URL-safe.
  - `token`: ≥ 160 bits de aleatoriedade (`secrets.token_urlsafe`).
  - `pepper_secret`: em `.env`, fora do banco; permite revogação por rotação.
- Por que HMAC e não `make_password`: o hash de senha (bcrypt/argon2) tem salt
  aleatório e **não** permite lookup direto por igualdade. HMAC-SHA256 com
  pepper é determinístico (buscável) e, com token de alta entropia, não é
  atacável por dicionário sem o pepper.
- Rotação/revogação: gerar novo token e substituir o hash do estudante; o token
  antigo deixa de existir. Não manter histórico de tokens válidos no MVP.

## 6. Estorno — modelagem

Optamos por **não** criar entidade separada de estorno no MVP (o plano lista
`DELIVERY` com campos `reversed_*`). O estorno é uma transição de estado da
própria `Delivery`, registrada também em `AuditEvent`:

- original permanece com todos os campos intactos;
- `status` vira `ESTORNADA`; preenche `reversed_at`, `reversed_by`,
  `reversal_reason`;
- indicadores operacionais contam apenas `status = VALIDA`;
- relatórios de controle exibem ambos.

Após estorno, o índice único parcial (§4.4) libera nova entrega regular para o
mesmo estudante na mesma distribuição — comportamento desejado.

## 7. Migrations — ordem prevista

```
0001 campus: Campus, ClassGroup
0002 accounts: User
0003 students: Student, ImportJob  (+ unique, index qr_token_hash)
0004 menus: Menu
0005 distributions: Distribution, Delivery (+ indexes, CheckConstraints, unique parcial)
0006 audit: AuditEvent
```
A migration `0005` inclui `RunSQL` das constraints parciais, com `reverse_sql`.
