---
name: user-config
description: Git configuration, environment variables, PATH components, and shell functions
metadata:
  type: rule
---

## Git Configuration

- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com)
- SSH signing key: `~/.ssh/id_ed25519.pub`
- Commit signing: GPG format SSH, always signed
- Pull strategy: rebase (`pull.rebase = true`)
- Allowed signers: `~/.ssh/allowed_signers`

## Environment Variables (defined in ~/.zshrc)

- `GOPATH=~/go`
- `VOLTA_HOME=$HOME/.volta` (Node version manager, used for pnpm, node)
- `EDITOR=vim`
- `GORGIAS_ROOT=/Users/guilhermebomfim/developer`
- `BAO_ADDR` — Vault address
- `GITHUB_PERSONAL_ACCESS_TOKEN` — populated via `gh auth token`
- `NPM_TOKEN` — GitHub npm registry auth

## PATH Components (in order)

- `$VOLTA_HOME/bin`
- `~/.local/bin`
- `~/.antigravity/antigravity/bin`
- `$PNPM_HOME` (`~/Library/pnpm`)
- `~/developer/gorgi`
- `/Applications/Visual Studio Code.app/Contents/Resources/app/bin`
- Orbstack shell init (`~/.orbstack/shell/init.zsh`)

## npm Registry

- `@gorgias` scope: registry at `https://npm.pkg.github.com/` (auth via `$NPM_TOKEN`)

## SSH Config

- Includes `~/.ssh/conductor_config` and `~/.orbstack/ssh/config`

## Shell Functions

- `dbproxy` — interactive fzf selector for cloud-sql-proxy connections
- `unify-ai-config` — symlinks AI config across tools (via `~/developer/dotfiles/unify-ai-config.mjs`)

## Project Aliases (defined in ~/.zshrc)

- `g:gorgias`, `g:chat`, `g:incoming`, `g:account-manager`, `g:workflows`, `g:help-center`, `g:helpdesk`, `g:ai-agent` — cd shortcuts to `~/developer/<project>`
- `g:proxy`, `g:proxy-chat`, `g:proxy-helpdesk` — local dev proxy launchers
- `g:pr`, `g:pr-checkout`, `g:pr-rebase` — PR tool shortcuts
- `g:ngrok`, `g:ngrok-tmux` — ngrok launchers
- `g:push-staging` — force-push staging branch

## Git Aliases (defined in ~/.zshrc)

- `gpo` — git push origin
- `gpof` — git push origin --force
- `gpfo` — git push --force-with-lease origin
- `grsoh` — git reset --soft HEAD^1
- `grbm` — fetch + rebase on origin/main with stash
- `gro` — fetch + rebase on origin/main
- `gcp` — git cherry-pick
- `grbi` — git rebase -i
- `grbc` — git rebase --continue
