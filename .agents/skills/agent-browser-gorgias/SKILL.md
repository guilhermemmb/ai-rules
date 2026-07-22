---
name: agent-browser-gorgias
description: Run agent-browser with a persistent profile so Gorgias logins survive across days. Use agent-browser-proxy variant to route through https://localhost:8001.
allowed-tools: Bash(agent-browser:*), Bash(command agent-browser:*), Bash(rm -rf ~/.agent-browser/profiles:*)
---

# agent-browser with Persistent Profile

## Rules (always apply when running agent-browser)

1. **Use the persistent profile path** for every agent-browser invocation:
   ```bash
   PROFILE="$HOME/.agent-browser/profiles/persistent"
   mkdir -p "$PROFILE"
   ```

2. **Always pass `--profile`**:
   ```bash
   agent-browser --profile "$PROFILE" open <url>
   agent-browser --profile "$PROFILE" snapshot -i
   agent-browser --profile "$PROFILE" screenshot output.png
   # etc.
   ```

3. **Cleanup stale date-based profiles** (legacy daily-rotation leftovers — never delete `persistent`):
   ```bash
   find "$HOME/.agent-browser/profiles" -maxdepth 1 -mindepth 1 -type d \
     ! -name persistent -exec rm -rf {} + 2>/dev/null || true
   ```

## agent-browser-proxy (with HTTPS proxy)

Same as above but add `--proxy "https://localhost:8001"`:

```bash
PROFILE="$HOME/.agent-browser/profiles/persistent"
mkdir -p "$PROFILE"
agent-browser --profile "$PROFILE" --proxy "https://localhost:8001" open <url>
```

## agent-browser-clean (manual reset)

When the user asks to clean or reset the browser profile:

```bash
agent-browser close 2>/dev/null || true
rm -rf "$HOME/.agent-browser/profiles"
echo "Profile wiped. Next agent-browser call will start fresh — Google login will be required again."
```

## agent-browser-gorgias-impersonate (login as any account)

Use when the user wants to log in to a specific Gorgias account by domain.

```bash
PROFILE="$HOME/.agent-browser/profiles/persistent"
mkdir -p "$PROFILE"

ACCOUNT_DOMAIN="{account_domain}"  # e.g. "acme" → acme.gorgias.com

agent-browser --profile "$PROFILE" open \
  "https://accounts.gorgias.com/impersonation?account_domain=${ACCOUNT_DOMAIN}"
agent-browser --profile "$PROFILE" wait --load networkidle
agent-browser --profile "$PROFILE" snapshot -i
```

- Replace `{account_domain}` with the subdomain (e.g. `acme` for `acme.gorgias.com`).
- The existing session in the persistent profile must already be authenticated; impersonation navigates directly without a password prompt.
- After navigating, take a snapshot or screenshot to confirm the impersonation succeeded.

## agent-browser-google-login (manual Google login)

Use when the session is expired or a Google login is required. Google blocks automated login, so the browser must be opened in **non-headless (headed) mode** so the user can log in manually.

```bash
PROFILE="$HOME/.agent-browser/profiles/persistent"
mkdir -p "$PROFILE"

# Open in headed (non-headless) mode so the user can complete Google login manually
agent-browser --profile "$PROFILE" --headed open "https://accounts.gorgias.com"
```

- The `--headed` flag is **mandatory** for Google login — headless mode will be blocked by Google.
- After the user completes login manually, the session is saved to the persistent profile and subsequent commands can run headlessly as normal — the login should survive across days.
- Inform the user: "The browser is now open. Please complete the Google login, then let me know when you're done."

## Example: Full session with persistent profile

```bash
PROFILE="$HOME/.agent-browser/profiles/persistent"
mkdir -p "$PROFILE"

# Cleanup legacy date-based profiles (never deletes persistent)
find "$HOME/.agent-browser/profiles" -maxdepth 1 -mindepth 1 -type d \
  ! -name persistent -exec rm -rf {} + 2>/dev/null || true

# Open and take screenshot
agent-browser --profile "$PROFILE" open https://app.example.com
agent-browser --profile "$PROFILE" wait --load networkidle
agent-browser --profile "$PROFILE" screenshot output.png
```
