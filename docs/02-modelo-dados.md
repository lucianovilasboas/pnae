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
id, campus_id FK, registration_number, full_name, email, cpf,
class_group_id FK (nullable), active,
created_at, updated_at
unique (campus_id, registration_number)
```
- O QR codifica `registration_number` (matrícula), que é o identificador único
  por campus usado na leitura; nome e CPF **não** aparecem no QR.
- `email` é usado pelo portal do aluno (opcional no MVP).

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

1. `unique (campus_id, registration_number)` em `Student` — sustenta a busca
   pela matrícula na leitura.
2. índice em `Delivery (distribution_id, student_id)`.
3. **índice único parcial** — a regra mais importante do MVP:
   ```sql
   CREATE UNIQUE INDEX uniq_regular_ativa
     ON distributions_delivery (distribution_id, student_id)
     WHERE delivery_type = 'REGULAR' AND status = 'VALIDA';
   ```
   Protege contra duas leituras concorrentes do mesmo QR. Excedente fica fora do
   índice (pode coexistir com a regular).
4. `CHECK (delivery_type IN ('REGULAR','EXCEDENTE'))` e
   `CHECK (status IN ('VALIDA','ESTORNADA'))`.
5. `CHECK` de excedente: `delivery_type <> 'EXCEDENTE' OR (reason IS NOT NULL
   AND authorized_by_id IS NOT NULL)`.
6. índice único parcial para uma única `Distribution` `OPEN` por
   `(campus_id, service_date, meal_type)`.

## 5. QR — decisão de conteúdo (RN-07)

- **Conteúdo do QR:** `Student.registration_number` (matrícula), identificador
  único por campus. A leitura busca por `(campus_id, registration_number)`.
- A matrícula é **identificador, não segredo**: não há token opaco nem hash no
  banco (a antiga `qr_token_hash` foi removida). A antifraude se apoia em aluno
  `active`, escopo de campus e no índice único parcial de entrega regular.
- **Consequência assumida:** matrículas são curtas/sequenciais; quem souber uma
  matrícula consegue montar o QR. Aceito explicitamente para simplificar o
  crachá e o portal do aluno (ver ADR-009 em `06-decisoes-abertas.md`).
- Nota histórica: o desenho anterior (token opaco de 160 bits + HMAC com
  `QR_PEPPER`) foi substituído; a `QR_PEPPER` deixa de ser usada.

## 6. Estorno — modelagem

Optamos por **não** criar entidade separada de estorno no MVP (o plano lista
`DELIVERY` com campos `reversed_*`). O estorno é uma transição de estado da
própria `Delivery`, registrada também em `AuditEvent`:

- original permanece com todos os campos intactos;
- `status` vira `ESTORNADA`; preenche `reversed_at`, `reversed_by`,
  `reversal_reason`;
- indicadores operacionais contam apenas `status = VALIDA`;
- relatórios de controle exibem ambos.

Após estorno, o índice único parcial (§4.3) libera nova entrega regular para o
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

## 8. Operações administrativas (editar/excluir/cancelar)

Regras implementadas nas telas de Distribuições e Cardápios:

- **Distribuição**
  - **Editar**: apenas em `RASCUNHO` (data, refeição, cardápio, horários,
    quantidade prevista). Auditado (`distribution.updated`).
  - **Excluir**: apenas em `RASCUNHO` e **sem entregas**. Auditado
    (`distribution.deleted`). Rascunhos com entregas ou fora de rascunho são
    bloqueados.
  - **Cancelar**: `RASCUNHO`/`ABERTA → CANCELADA`, com **motivo** (guardado no
    `AuditEvent`). Cancelada não aceita leitura. Auditado
    (`distribution.canceled`).
  - **Encerrada**: só **reabre no mesmo dia** (`distribution.reopened`).
  - **Auto-encerramento**: ao abrir as telas, distribuições `ABERTA` com
    `service_date` anterior a hoje vão para `ENCERRADA` com
    `closed_by=null` e auditoria (`distribution.auto_closed`). Não depende de
    cron.
- **Cardápio**
  - **Editar**: respeita o único `(campus, service_date, meal_type)`;
    auditado (`menu.updated`).
  - **Excluir**: bloqueado se houver **distribuição vinculada**; auditado
    (`menu.deleted`).
- **Estudante** (tela de Estudantes, administrador)
  - **Criar/Editar**: matrícula, nome, e-mail, curso, turma e situação `ativo`
    (`campus` vem do escopo do usuário). Auditado (`student.created` /
    `student.updated`).
  - **Inativar**: `active=false` (sem DELETE físico, RN-09); reativação pela
    própria edição. Auditado (`student.deactivated`).
  - A unicidade `(campus, registration_number)` continua sendo a fonte de
    verdade; matrícula repetida é recusada com aviso.

> Entregas e importações permanecem **sem exclusão física** (RN-09); as
> exclusões acima são de entidades administrativas e sempre geram auditoria.
