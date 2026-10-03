# 07 — Segurança, LGPD e operação

Controles concretos para o §10 do [plano do MVP](../plano_mvp_ifmg_alimenta.md).

## 1. Transporte e segredos

- HTTPS obrigatório em todo ambiente não local (TLS no Traefik).
- `.env` nunca versionado (só `.env.example`); segredos fora do repositório.
- `SECRET_KEY` e senha do banco vindos do ambiente.
- Nada de segredo em código, template ou log.

## 2. QR do estudante

- O QR codifica a **matrícula** (identificador único por campus), que **não é
  segredo** (ver ADR-009 e `02-modelo-dados.md` §5).
- A antifraude não depende de sigilo do QR: apoia-se em aluno `active`, escopo
  de campus e no índice único parcial de entrega regular.
- Nenhum token/segredo por aluno é armazenado.

## 3. Autenticação e autorização

- Senhas com hasher forte do Django (Argon2/PBKDF2); nunca logar senha.
- Sessão segura (`SESSION_COOKIE_SECURE`, `HTTPONLY`, `SAMESITE`), CSRF ativo.
- Autorização por campus em **toda** query e mutação (admin global é exceção
  explícita).
- Permissões `can_authorize_extras` e `can_reverse_deliveries` checadas no
  service, não só na UI.
- Reautenticação para autorizar excedente/estornar quando exigido pela
  instituição (decisão aberta nº 4).

## 4. Minimização (LGPD)

- QR contém a matrícula (identificador), mas **não** nome, CPF nem turma.
- Operação exibe apenas nome/matrícula/turma, o mínimo para reduzir erro.
- Exportações exigem permissão e retornam só as colunas necessárias.
- `AuditEvent.metadata_json` guarda o essencial (sem dado pessoal excessivo).
- Testes e exemplos usam **apenas dados anonimizados**.

## 5. Auditoria

Toda operação relevante gera `AuditEvent` com ator, data/hora, entidade, ação e
antes/depois quando aplicável (RN-11):

- entregas, excedentes, estornos;
- abertura/encerramento/cancelamento de distribuição;
- importações aplicadas;
- mudanças administrativas de usuários/estudantes/parâmetros.

Eventos são imutáveis: sem `UPDATE`/`DELETE` na aplicação.

## 6. Banco e concorrência

- Índice único parcial valida a entrega regular única (ver `02-modelo-dados.md`).
- `/scan` transacional; a constraint decide empates concorrentes.
- Backups automatizados e **restauração testada** ao menos uma vez antes do
  piloto.
- Política de retenção de entregas/auditoria definida pelo campus (decisão
  aberta nº 7).

## 7. Operação

- Ambiente prod sem portas de banco expostas; Postgres gerenciado ou com backup.
- Logs de aplicação sem PII e sem segredos; nível adequado por ambiente.
- Monitorar erros 5xx e falhas de leitura; alerta para indisponibilidade.
- Contingência documentada para internet/energia no ponto de distribuição
  (procedimento manual temporário + reconciliação; offline é pós-MVP).

## 8. Checklist antes do piloto

- [ ] HTTPS ativo e cookies seguros.
- [ ] `DEBUG=False`; `ALLOWED_HOSTS` restrito.
- [ ] Segredos fora do repositório; `.env` não versionado.
- [ ] Permissões por campus verificadas em todas as rotas.
- [ ] Nenhum dado pessoal (nome/CPF/senha) em logs e respostas.
- [ ] Teste de concorrência verde (ver `05-testes.md`).
- [ ] Backup + restauração testados.
- [ ] Responsável institucional pelos dados e base legal definidos (§10.7).
