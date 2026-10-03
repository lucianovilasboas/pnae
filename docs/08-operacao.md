# 08 — Operação e runbook

Procedimentos para operar, publicar e recuperar o IFMG Alimenta. Complementa o
checklist de segurança em [`07-seguranca-lgpd.md`](07-seguranca-lgpd.md).

## 1. Ambientes

- **dev:** `docker compose -f docker-compose.dev.yml up -d --build`
  (http://127.0.0.1:8601, contêiner `pnae_app_django`, banco `pnae_db`).
- **prod:** `docker compose up -d --build` (atrás do Traefik, sem portas
  expostas). `DJANGO_SETTINGS_MODULE=config.settings.prod`, `DEBUG=False`.

## 2. Backup do banco

```bash
./scripts/backup_db.sh
```

- Gera `backups/pnae-AAAAMMDD-HHMMSS.sql.gz` via `pg_dump` dentro do
  contêiner `pnae_db`.
- Retenção padrão: 14 arquivos (`BACKUP_KEEP`).
- **Agendar** (cron diário, exemplo):
  `0 2 * * * cd /caminho/pnae_app && ./scripts/backup_db.sh >> backups/backup.log 2>&1`

## 3. Restauração (testada)

Restaura para um banco **separado** (não toca no banco em uso), permitindo
validar o backup:

```bash
./scripts/restore_db.sh backups/pnae-AAAAMMDD-HHMMSS.sql.gz
```

- Cria/recria `django_db_restore` e importa o dump.
- Ao final, imprime as contagens de `students_student` e
  `distributions_delivery` — devem conferir com o momento do backup.
- **Testar a restauração antes do piloto** e registrar o resultado.

## 4. Ensaio operacional (≥ 50 leituras)

```bash
docker exec pnae_app_django python manage.py pilot_drill --campus PN --students 60
```

- Cria estudantes sintéticos `DRILL-*` (não usa os estudantes reais nem seus
  QR), abre uma distribuição, executa N leituras + releituras (duplicidade) +
  excedentes + estornos, confere a coerência dos totais e encerra.
- `--cleanup` remove os dados do ensaio.
- Encerra com erro se os totais não fecharem.

## 5. Carga de estudantes

```bash
docker exec pnae_app_django python manage.py import_roster /pnae_app/alunos.xlsx \
    --campus PN --campus-name "IFMG — Campus Ponte Nova" --academic-year 2026 \
    --user luciano.espiridiao@ifmg.edu.br --dry-run
```
Remova `--dry-run` para aplicar. A prévia não altera a base; a aplicação cria
turmas e faz upsert por matrícula (idempotente).

## 6. Deploy (produção)

1. `cp .env.example .env` e preencher (em especial `SECRET_KEY`,
   `DATABASE_URL`, `ALLOWED_HOSTS`, `USE_HTTPS_PROXY=True`,
   `CSRF_TRUSTED_ORIGINS=https://<domínio>`).
2. `docker compose up -d --build` (o `entrypoint.sh` roda `migrate` e
   `collectstatic`).
3. `docker exec pnae_app python manage.py createsuperuser`.
4. Conferir o domínio/HTTPS nos labels do Traefik (`docker-compose.yml`).

## 6.1 Leitura por câmera do celular (HTTPS obrigatório)

O navegador só libera a câmera em **HTTPS** (ou `localhost`). Para testar no
celular sem domínio próprio, use o Tailscale:

```bash
tailscale serve --bg --https=8443 8601      # publica o app em https://<máquina>.<tailnet>.ts.net:8443
```

Depois, no `.env`, inclua o host e a origem e recrie o container:

```
ALLOWED_HOSTS=...,<máquina>.<tailnet>.ts.net
CSRF_TRUSTED_ORIGINS=...,https://<máquina>.<tailnet>.ts.net:8443
```

A leitura por câmera usa **ZXing** (QR Code + códigos de barras 1D) e funciona
em iOS/Safari e Android/Chrome. Ver `static/vendor/zxing/README.txt`.


## 7. Contingência (internet/energia no ponto)

- Internet indisponível: registrar em papel (matrícula + hora) e reconciliar no
  sistema assim que voltar. Offline/sincronização é pós-MVP.
- Manter o procedimento manual impresso no ponto de distribuição.
- Após reconexão: lançar as entregas normais e usar excedente/estorno apenas
  via fluxo auditável.

## 8. Rotinas de verificação

| Rotina | Como |
|---|---|
| Saúde da aplicação | `GET /healthz/` → `{"status":"ok","database":true}` |
| Backup recente | `ls -lt backups \| head` |
| Restauração válida | `./scripts/restore_db.sh <backup>` e conferir contagens |
| Ensaio de volume | `python manage.py pilot_drill --campus PN --students 60` |
| Auditoria | `/auditoria/` (admin/gestor) |

## 9. Hardening antes do piloto

- `DEBUG=False`, `ALLOWED_HOSTS` restrito, HTTPS e cookies seguros.
- `SECRET_KEY` forte; banco sem portas expostas em produção.
- Rodar `python manage.py check --deploy` e tratar os avisos.
