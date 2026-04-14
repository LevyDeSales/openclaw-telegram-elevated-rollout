# openclaw-telegram-elevated-rollout

Skill repo para rollout controlado de `tools.elevated` via Telegram em ambientes OpenClaw locais.

## Estrutura

- `SKILL.md`: definição principal da skill
- `scripts/`: utilitários de inspeção, preflight, apply e validação
- `references/`: escopo suportado, troubleshooting e limites de validação

## Input operacional

O repositório não publica um sender real de Telegram.

Passe o identificador explicitamente:

```bash
export TELEGRAM_SENDER_ID="SEU_TELEGRAM_SENDER_ID"
```

Ou informe `--sender SEU_TELEGRAM_SENDER_ID` nos scripts Python.

## Fluxo Git recomendado

Este repositório usa duas branches fixas:

- `prod`: branch estável, usada como referência de publicação
- `dev`: branch de trabalho e integração

Regra prática:

1. mudanças novas entram em `dev`
2. validação local acontece em `dev`
3. quando estiver estável, `dev` é mesclada em `prod`
4. `prod` é a branch que representa a versão pronta para compartilhar

## Setup local do Git

Se o diretório ainda não for um repositório Git:

```bash
git init -b prod
git switch -c dev
git switch prod
```

Se o repositório já existir e só faltarem as branches:

```bash
git branch prod
git branch dev
git switch dev
```

## Primeiro commit

Depois de revisar os arquivos:

```bash
git switch dev
git add .
git commit -m "chore: bootstrap skill repo"
```

## Publicação no GitHub

Crie um repositório vazio no GitHub e conecte o remoto:

```bash
git remote add origin <URL_DO_REPOSITORIO>
git push -u origin dev
git push -u origin prod
```

Exemplo de URL:

```bash
git remote add origin git@github.com:SEU_USUARIO/openclaw-telegram-elevated-rollout.git
```

Ou:

```bash
git remote add origin https://github.com/SEU_USUARIO/openclaw-telegram-elevated-rollout.git
```

Se preferir criar o repositório pelo GitHub CLI:

```bash
gh auth login -h github.com
gh repo create openclaw-telegram-elevated-rollout --private --source=. --remote=origin --push
```

Depois confirme se as duas branches foram publicadas:

```bash
git push -u origin dev
git push -u origin prod
```

## Fluxo do dia a dia

Para trabalhar:

```bash
git switch dev
git pull --ff-only origin dev
```

Para promover para produção:

```bash
git switch prod
git merge --ff-only dev
git push origin prod
```

Se quiser manter `prod` estritamente linear, prefira `merge --ff-only` e faça toda a integração antes em `dev`.

## Checklist antes de promover `dev` para `prod`

- scripts revisados
- escopo da skill atualizado em `SKILL.md`
- referências coerentes com o comportamento real
- validação local concluída para o fluxo alterado

## Observação importante

Este repositório documenta uma skill operacional. Não trate merge em `prod` como prova de sucesso em runtime no Telegram; a separação entre prova de configuração e prova em chat continua valendo conforme `references/validation-boundaries.md`.
