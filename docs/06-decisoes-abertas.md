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

- **Status:** aceito (ver `02-modelo-dados.md` §5).
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

- **Status:** proposto.
- **Contexto:** evitar pipeline de front no início.
- **Decisão:** Tailwind via CDN no MVP; migrar para build standalone (npm)
  quando a UI estabilizar.
- **Consequência:** leve penalidade de performance aceitável; dívida registrada.

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
