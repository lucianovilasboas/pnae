# 06 — Decisões abertas e ADRs

Perguntas institucionais (§14 do [plano do MVP](../plano_mvp_ifmg_alimenta.md))
e decisões técnicas pendentes. Enquanto abertas, cada uma tem um **default
proposto** para não travar a implementação; confirmar antes do piloto.

## A. Decisões institucionais

| # | Pergunta | Default proposto | Status |
|---|---|---|---|
| 1 | Campus e tipos de refeição do piloto | Ponte Nova (PN), `meal_type=SNACK` (lanche) | ✅ |
| 2 | Fonte oficial de estudante/matrícula/turma/situação | planilha da secretaria (XLSX) | ⏳ |
| 3 | Formatos reais de CSV/XLSX | aceitar ambos; mapear colunas na importação | ⏳ |
| 4 | Quem autoriza excedente/estorno; login individual ou PIN | permissão individual + reautenticação por senha | ⏳ |
| 5 | Entrega para visitante/servidor/sem QR | fora do MVP; exige decisão explícita | ⏳ |
| 6 | Mais de uma refeição no mesmo dia em sessões distintas | permitido (chave é a distribuição) | ⏳ |
| 7 | Retenção de entregas/auditoria | ≥ 5 anos (prestação de contas PNAE) | ⏳ |
| 8 | Hospedagem e responsável por backups/contas | cluster Docker + Traefik; backup diário | ⏳ |
| 9 | Assinatura/layout do relatório diário | página imprimível + CSV; PDF depois | ⏳ |
| 10 | Dispositivos do ponto de distribuição | scanner USB primário + celular (câmera) | ⏳ |

## B. ADRs (decisões técnicas)

### ADR-001 — Autenticação por sessão (não JWT)

- **Status:** aceito.
- **Contexto:** UI em templates/HTMX; endpoints JSON pontuais.
- **Decisão:** sessão Django com cookies seguros; mesma sessão nos endpoints
  JSON.
- **Consequência:** sem infraestrutura de tokens; CSRF obrigatório.

### ADR-002 — Token QR como HMAC-SHA256 com pepper

- **Status:** substituído pelo ADR-009 (o QR passou a codificar a matrícula).
- **Contexto:** precisa buscar pelo hash na leitura e não guardar o token.
- **Decisão:** `HMAC-SHA256(pepper, token)`, token com ≥ 160 bits.
- **Consequência:** lookup determinístico; pepper no ambiente; rotação revoga.

### ADR-003 — Unicidade garantida por índice único parcial

- **Status:** aceito.
- **Decisão:** constraint no Postgres por `(distribution_id, student_id)` onde
  `delivery_type='REGULAR' AND status='VALIDA'`.
- **Consequência:** `/scan` interpreta `IntegrityError`; app não confia apenas
  em checagem prévia.

### ADR-004 — Tailwind: CDN no MVP, build depois

- **Status:** parcial — self-hosted implementado; build real (npm) pendente.
- **Contexto:** evitar pipeline de front no início; o CDN externo (407 KB,
  render-blocking) piorava a latência e o service worker não o cacheava.
- **Decisão:** manter a compilação em runtime, mas **self-hospedar** o
  `tailwind.js` em `static/vendor/tailwind/` (sem Node, cacheável pelo PWA);
  migrar para build standalone (npm) quando estabilizar.
- **Consequência:** remove a dependência de rede por página; a compilação em
  runtime ainda ocorre no cliente na primeira carga. Dívida registrada.

### ADR-005 — Estorno como transição de estado (sem entidade separada)

- **Status:** aceito (ver `02-modelo-dados.md` §6).
- **Consequência:** `Delivery.status=ESTORNADA` + `AuditEvent`; original
  preservado.

### ADR-006 — App instalável (PWA), sem operação offline

- **Status:** aceito (implementado).
- **Decisão:** `manifest` + ícones + service worker instalável no celular e no
  desktop; cache **apenas** de estáticos. Navegação e APIs (`/api/*`, `/scan`,
  `/healthz`) sempre vão à rede — nenhuma operação offline no MVP.
- **Rotas:** `/manifest.webmanifest` e `/service-worker.js`.

### ADR-007 — QR permanece token opaco; matrícula é exibida, não codificada

- **Status:** substituído pelo ADR-009.
- **Contexto:** desejo de usar a matrícula como identificador do QR. A matrícula
  é curta/sequencial; se for o segredo, torna-se forjável e contraria a RN-07
  ("QR contém token aleatório/opaco; matrícula nunca codificada") e o doc 07 §4.
- **Decisão:** manter o `token` opaco de 160 bits no QR e **exibir a matrícula
  como número** ao lado do QR (na folha de exportação e, futuramente, no portal
  do aluno). A leitura continua buscando por `qr_token_hash`.
- **Consequência:** antifraude preservada; nenhuma mudança em `/scan` ou no
  modelo. A matrícula é identidade visível, não credencial.

### ADR-008 — Portal do aluno e publicação de cardápio

- **Status:** aceito (implementado; antes listado como fora do MVP).
- **Contexto:** o aluno passa a acessar pelo celular o cardápio e o próprio QR.
- **Decisões:**
  - login do aluno por **e-mail + senha**, com senha definida no **primeiro
    acesso**; primeiro acesso e recuperação provam identidade por
    **matrícula + CPF** (sem envio de e-mail).
  - conta própria do aluno (`StudentAccount`, OneToOne com `Student`), com
    **sessão isolada** (`portal_account_id`) do `accounts.User` da equipe;
  - cardápio só aparece ao aluno quando o operador marcar **publicado** no
    `Menu` (controle explícito, não automático por data);
  - o portal mostra hoje, amanhã e a semana atual, além do **QR (matrícula) +
    o número** em destaque.
- **Consequência:** nova app `apps/portal`, `Menu.published` e throttle básico
  no login/primeiro acesso. Base legal LGPD e política de uso a formalizar com a
  instituição antes de divulgar aos alunos.

### ADR-009 — QR codifica a matrícula do estudante

- **Status:** aceito (supersede ADR-002 e ADR-007).
- **Contexto:** o aluno passa a usar o próprio celular como crachá e o QR deve
  ser simples de exibir (portal, folha impressa) sem segredo por aluno.
- **Decisão:** o conteúdo do QR é `Student.registration_number`; a leitura
  busca por `(campus_id, registration_number)`. A `qr_token_hash` e o token
  opaco foram removidos.
- **Consequência assumida:** a matrícula é adivinhável (baixa entropia), então
  o QR **não é segredo** — a antifraude se apoia em aluno `active`, escopo de
  campus e no índice único parcial de entrega regular. RN-07 e o doc 07 §4 foram
  atualizados; os crachás antigos (token) foram reimpressos.
