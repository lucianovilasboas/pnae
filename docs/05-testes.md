# 05 — Estratégia de testes

Objetivo: provar as regras inegociáveis do MVP, em especial o **bloqueio
transacional de duplicidade**. Dados **sempre anonimizados**.

## 1. Ferramentas

- `pytest` + `pytest-django` para unit/integração (ou runner do Django).
- `factory_boy` (ou factories simples) para massa de teste.
- Banco de teste: PostgreSQL (as constraints parciais do §4 do modelo **não**
  existem no SQLite; testar contra Postgres é obrigatório).
- E2E opcional: Playwright para a tela de operação.

Comando-alvo (a registrar quando o scaffold existir):

```bash
docker exec app_django bash -lc 'cd /pnae_app && python manage.py test -v 1'
```

## 2. Pirâmide

| Nível | Foco |
|---|---|
| Unitário | hash do token, regras de estado, permissões, cálculos de `summary` |
| Integração | services + ORM + constraints reais no Postgres |
| E2E (opcional) | fluxo de scanner na tela de operação |

## 3. Casos obrigatórios por regra

| Regra | Caso de teste |
|---|---|
| RN-02 | `/scan` em `DRAFT`/`CLOSED` → `DISTRIBUTION_CLOSED`, sem entrega |
| RN-03 | 2ª leitura regular → `ALREADY_DELIVERED`, sem nova entrega |
| RN-04 | duplicidade não cria `Delivery` |
| RN-05 | excedente sem motivo/autorizador → rejeitado |
| RN-06 | excedente com distribuição fechada → rejeitado |
| RN-07 | resposta e logs não contêm token bruto |
| RN-08 | estudante inativo/outro campus → `INELIGIBLE` |
| RN-09 | estorno não apaga; `status=ESTORNADA` e original intacto |
| RN-10 | horários em UTC; exibição no fuso do campus |
| RN-11 | operação relevante grava `AuditEvent` |
| RN-12 | exportação restrita por permissão e colunas mínimas |

## 4. Teste de concorrência (crítico)

Prova que a **constraint do banco**, e não a aplicação, garante a unicidade:

1. criar `Distribution` `OPEN` e `Student` ativo com token conhecido;
2. disparar **duas** chamadas concorrentes ao service de `/scan` com o mesmo
   token (duas threads/conexões, `transaction.atomic` independentes);
3. resultado esperado:
   - exatamente **uma** `Delivery REGULAR VALIDA` existe;
   - uma chamada retorna `DELIVERED` e a outra `ALREADY_DELIVERED`;
4. repetir o teste sem a constraint deve falhar (prova de valor) — manter como
   teste de regressão do schema.

```python
# Esboço (implementar na Fase 2)
def test_duas_leituras_concorrentes_geram_uma_entrega(distribution, student):
    results = run_two_concurrent_scans(distribution.id, student.token)
    assert sorted(results) == ["ALREADY_DELIVERED", "DELIVERED"]
    assert Delivery.objects.filter(
        distribution=distribution, student=student,
        delivery_type="REGULAR", status="VALIDA",
    ).count() == 1
```

## 5. Teste de importação

- CSV/XLSX válido → aplica; contadores corretos.
- linhas com matrícula duplicada, campos vazios e turma inexistente → rejeitadas
  com relatório, sem alterar a base na fase de prévia.

## 6. Teste de estorno

- estorno exige motivo;
- original permanece `VALIDA`? **não** → vira `ESTORNADA` com `reversed_*`;
- após estorno, nova entrega regular é permitida (índice parcial libera).

## 7. Critérios de aceite dos marcos (ver `04-marcos.md`)

- **M1:** importar base de teste, imprimir QR, impedir matrícula duplicada.
- **M2:** ≥ 50 leituras simuladas, duplicidade bloqueada, totais coerentes,
  teste de concorrência verde.
- **M3:** relatório reconcilia regulares + excedentes + estornos.
- **M4:** operação sem apoio técnico; backup/restauração testados.
