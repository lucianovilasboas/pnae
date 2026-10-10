# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e versionamento [SemVer](https://semver.org/lang/pt-BR/).
A versão corrente é a constante `APP_VERSION` em `config/version.py`.

## [1.0.0] - 2026-10-10

### Added
- Versão do sistema exibida no rodapé (desktop) e no menu (mobile).
- `CHANGELOG.md` para acompanhar as versões.
- Botão "+" ao lado do campo Cardápio que abre um **pop-up** para cadastrar um
  cardápio único sem sair da tela (preserva os valores já preenchidos); ao
  salvar, o cardápio novo entra no select.
- Seletor de campus para administrador global quando há mais de um campus
  ativo (nas telas de Distribuições e de Cardápios).

### Changed
- Tela de Distribuições: **Data**, **Início previsto** e **Fim previsto** na
  1ª linha; **Refeição** e **Cardápio (opcional)** na 2ª linha — layout mais
  compacto.
- Início/Fim previstos agora exibem apenas o horário (a data vem do campo
  Data); a mesma simplificação foi aplicada à edição do rascunho.
- A ação "Cadastrar cardápio" deixou de ficar ao lado de "Criar rascunho" e
  passou para junto do campo Cardápio.

### Fixed
- Erro "Campus não definido." ao cadastrar cardápio por administrador global
  em base com mais de um campus ativo.
