"""Motivos sugeridos (excedente e estorno).

Fonte única usada pelas telas de operação e de entregas. São apenas sugestões:
o campo continua livre e o que o usuário digita é memorizado no aparelho
(localStorage), sem ir para o banco.
"""

EXTRA_REASONS = (
    "Aluno sem o QR/carteirinha",
    "Segunda refeição",
    "Reposição de refeição",
    "Autorizado pela gestão",
)

REVERSAL_REASONS = (
    "Entrega registrada por engano",
    "QR lido duas vezes",
    "Estudante incorreto",
    "Aluno recusou a refeição",
)
