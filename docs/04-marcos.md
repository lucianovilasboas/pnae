# 04 — Marcos e tarefas de engenharia

Os Marcos 0–4 do §11 do [plano do MVP](../plano_mvp_ifmg_alimenta.md) quebrados
em tarefas executáveis, cada uma com entregável e critério de verificação.
Seguir o fluxo de branch de `AGENTS.md` (`feat/*`, nunca direto na `main`).

Legenda de verificação: `V:` = como confirmar que a tarefa está feita.

---

## Marco 0 — Descoberta e decisões (1–3 dias)

Sem código. Destrava o backend.

- [ ] **M0.1** Validar processo real no refeitório (picos, operadores,
  dispositivos, conectividade, exceções). `V:` ata de reunião registrada em
  `docs/06-decisoes-abertas.md`.
- [ ] **M0.2** Obter amostra **anonimizada** da planilha atual. `V:` arquivo de
  exemplo (anonimizado) usado nos testes.
- [ ] **M0.3** Confirmar campos mínimos de estudante e convenção de turma.
  `V:` decisão fechada em `06-decisoes-abertas.md`.
- [ ] **M0.4** Decidir quem autoriza excedentes/estornos. `V:` permissões
  definidas por perfil.
- [ ] **M0.5** Definir nomenclatura de refeições e formato do relatório.
  `V:` enum `meal_type` e layout do relatório aprovados.
- [ ] **M0.6** Aprovar protótipo navegável da tela de operação. `V:` protótipo
  aceito pelo usuário.

**Saída:** backlog priorizado, critérios de aceite e dados de importação.

---

## Marco 1 — Fundamentos (3–5 dias)

- [x] **M1.1** Scaffold Django + Docker Compose dev/prod + `.env.example`.
  `V:` `docker compose up` sobe app e Postgres.
- [x] **M1.2** App `campus`: `Campus`, `ClassGroup` + migrations + admin.
  `V:` criar campus/turma no admin.
- [x] **M1.3** App `accounts`: `User` custom, papéis e permissões extras;
  login/logout. `V:` login por e-mail e bloqueio por papel.
- [x] **M1.4** App `students`: `Student` + constraints (`unique` por campus,
  índice `qr_token_hash`). `V:` migration aplica as constraints.
- [x] **M1.5** Geração de token QR + `qr_token_hash` (HMAC com pepper).
  `V:` teste unitário do hash e do gerador.
- [x] **M1.6** Importação CSV/XLSX com prévia e relatório de rejeitadas
  (`ImportJob`). `V:` importar arquivo de teste; linhas ruins rejeitadas.
- [x] **M1.7** Exportação de QR (folha de impressão). `V:` gerar e imprimir um
  lote; QR lido confere com o estudante.
- [ ] **M1.8** App `audit` + `AuditEvent`; log de ações administrativas.
  Modelo, admin e `record_event` prontos; eventos de importação e QR já
  gravados. Falta instrumentar as demais ações administrativas.
  `V:` eventos gravados ao criar/editar.

> Importação e QR entregues na branch `feat/students-import-qr`: importer
> CSV/XLSX com prévia/aplicação em duas fases, folha de impressão de QR com
> rotação explícita de token, endpoints JSON e páginas para administrador.
> Rotação de token invalida QRs antigos por decisão (ADR-002).

> Scaffold inicial entregue na branch `feat/scaffold-django`: modelos,
> migrations (incl. índices únicos parciais), admin e 10 testes verdes
> (`docs/05-testes.md`). Modelos de `menus` e `distributions` também já
> existem, mas a lógica de negócio (M2) ainda não.

**Aceite do marco:** importar uma base de teste, localizar estudante, imprimir
QR e impedir matrícula duplicada.

---

## Marco 2 — Núcleo de distribuição (4–6 dias)

- [x] **M2.1** App `menus`: `Menu` + admin. `V:` CRUD de cardápio.
- [x] **M2.2** App `distributions`: `Distribution` com máquina de estados e
  índice único parcial de `OPEN`. `V:` não permite duas `OPEN` iguais.
- [x] **M2.3** `Delivery` + constraints (índice único parcial `REGULAR VALIDA`,
  checks). `V:` migration aplica a constraint.
- [x] **M2.4** Service do `/scan` atômico (ver `03-api.md` §4).
  `V:` teste de integração das 5 respostas de negócio.
- [x] **M2.5** Tela de operação (HTMX/JS): campo focado, recuperação de foco,
  scanner USB, botão de câmera (BarcodeDetector quando disponível), feedback
  verde/vermelho/amarelo. `V:` simular leitura por teclado e conferir feedback.
- [x] **M2.6** Painel de totais ao vivo (`summary`). `V:` totais coerentes após
  leituras.
- [x] **M2.7** Teste de concorrência de duplicidade. `V:` ver `05-testes.md`
  (§4); exatamente uma entrega `REGULAR` válida.

> Marco 2 entregue na branch `feat/distributions-scan`: serviços transacionais
> (criar/abrir/encerrar, `/scan`, excedente, estorno, resumo, pendentes),
> endpoints JSON, tela de operação, lista de distribuições e lista de
> pendentes. Inclui teste de concorrência real (`TransactionTestCase` com
> threads) que prova a unicidade pela constraint do banco.

**Aceite do marco:** simulação de ≥ 50 leituras com entrega correta,
duplicidade bloqueada e totais coerentes.

---

## Marco 3 — Excedentes, correção e relatório (3–5 dias)

- [ ] **M3.1** Autorização de excedente com motivo e autorizador
  (`extras`). `V:` excedente sem motivo/autorizador é rejeitado.
- [ ] **M3.2** Estorno auditável (`reverse`): original preservado.
  `V:` estorno não apaga; nova regular liberada após estorno.
- [ ] **M3.3** Lista de pendentes com filtro por turma. `V:` pendentes batem com
  `summary`.
- [ ] **M3.4** Relatório diário (página imprimível + CSV/PDF).
  `V:` reconcilia regulares, excedentes e estornos com o histórico de eventos.
- [ ] **M3.5** Tela de auditoria com filtros (data, usuário, entidade, ação).
  `V:` localizar um evento pelo filtro.

**Aceite do marco:** relatório reconcilia entregas regulares, excedentes e
estornos com o histórico de eventos.

---

## Marco 4 — Piloto e estabilização (5–10 dias, conforme operação)

- [ ] **M4.1** Homologação com dados reais controlados.
  `V:` importação real sem duplicidade não tratada.
- [ ] **M4.2** Ensaio operacional e treinamento curto. `V:` operador executa o
  fluxo sem apoio técnico.
- [ ] **M4.3** Piloto em uma distribuição. `V:` sessão real concluída.
- [ ] **M4.4** Correções de usabilidade e publicação.
  `V:` checklist de segurança (`07-seguranca-lgpd.md` §8) completo.
- [ ] **M4.5** Backup + restauração testados. `V:` restauração bem-sucedida
  registrada.

**Aceite de produção:** operador opera sem apoio técnico; backup e contingência
documentados.

---

## Ordem de dependências

```
M0 ─▶ M1.1 ─▶ M1.2 ─▶ M1.3 ─▶ M1.4 ─▶ M1.5 ─▶ M1.6 ─▶ M1.7 ─▶ M1.8
                                                              │
                                             M2.1 ◀───────────┘
                                               │
                                               ▼
                        M2.2 ─▶ M2.3 ─▶ M2.4 ─▶ M2.5 ─▶ M2.6 ─▶ M2.7
                                                              │
                                                              ▼
                                             M3.1 ─▶ M3.2 ─▶ M3.3 ─▶ M3.4 ─▶ M3.5
                                                              │
                                                              ▼
                                                            M4.x
```

> Estimativa indicativa total: **3 a 5 semanas** de calendário, variando com
> dados, decisões institucionais, hospedagem e piloto.
