# HA API Client (`/ha-api`)

Use when you need to interact with Home Assistant from Node.js scripts — automations CRUD, dashboard get/save, and device/area/entity registry operations.

## Quick Reference

```js
import ha from './api/index.js'
// ha is a singleton — no configure() needed; reads token from ha-auth.json automatically
```

**Working directory:** `~/developer/ha/`
**API directory:** `~/developer/ha/api/`

---

## Auth

Token is resolved in this order:
1. `ha.configure({ token: '...', url: '...' })` — explicit override
2. `HA_TOKEN` env var — long-lived token from HA profile page
3. `ha-auth.json` — reads `refresh_token`, auto-refreshes and caches `access_token`

The `ha-auth.json` format stores tokens inside `origins[0].localStorage[name=hassTokens].value` (browser localStorage format).

---

## Automations

> **Note:** HA's `/api/config/automation/config` (list endpoint) returns 404 on this instance.
> `automations.list()` fetches IDs from `/api/states` then fetches each config individually.

```js
// Fast — IDs + names only (no config details)
const summary = await ha.automations.listSummary()
// [{ entity_id, id, name }, ...]

// Full configs (parallel fetches per automation)
const all = await ha.automations.list()

// Single automation by storage ID (from listSummary or attributes.id)
const auto = await ha.automations.get('1773602263472')

// Update (POST with full config object)
await ha.automations.update('1773602263472', { ...auto, alias: 'New name' })

// Create (POST without id — HA assigns one)
await ha.automations.create({ alias: 'Test', triggers: [...], actions: [...] })
```

---

## Dashboard

> **Note:** REST `/api/lovelace/config` returns 404. Both get and save use WebSocket.

```js
// Get dashboard config by url_path
const config = await ha.dashboard.get('dashboard-test')
// Returns the lovelace config object ({ views: [...] })

// Save (mutates in place)
await ha.dashboard.save('dashboard-test', { ...config, views: [...] })
```

**Known url_paths on this instance:**
- `dashboard-test` — patylherme dashboard (main, mobile-first, 7 views)
- `patylherme-home` — auto-states placeholder (original-states strategy)

---

## Registry

All via WebSocket (`config/*_registry/*`).

```js
// Areas
const areas = await ha.registry.listAreas()
// [{ area_id, name, aliases, icon, ... }]

// Devices
const devices = await ha.registry.listDevices()
// [{ id, name, area_id, manufacturer, model, ... }]

// Update device (rename, move to area)
await ha.registry.updateDevice('abc123', { name: 'New Name', area_id: 'living_room' })

// Entities (optional filter)
const all = await ha.registry.listEntities()
const lights = await ha.registry.listEntities({ domain: 'light' })
const inRoom = await ha.registry.listEntities({ area_id: 'kitchen' })
const ofDevice = await ha.registry.listEntities({ device_id: 'abc123' })
```

**Known area IDs:** `living_room`, `kitchen`, `bedroom`, `office_room`, `paty_office`, `balcony`, `main_hallway`

---

## WebSocket Internals

`websocket.js` maintains a single persistent connection per process. Call `ha.close()` when done to cleanly teardown the WebSocket.

```js
// Always close at end of script
ha.close()
```

The connection auto-reconnects if reused after close.

---

## Common Patterns

### List all automations with full config
```js
cd ~/developer/ha
node -e "
import('./api/index.js').then(async m => {
  const ha = m.default
  const autos = await ha.automations.list()
  console.log(JSON.stringify(autos, null, 2))
  ha.close()
})"
```

### Rename a device and move it to an area
```js
import ha from './api/index.js'
const devices = await ha.registry.listDevices()
const device = devices.find(d => d.name === 'Old Name')
await ha.registry.updateDevice(device.id, { name: 'New Name', area_id: 'kitchen' })
ha.close()
```

### Read and patch a dashboard view title
```js
import ha from './api/index.js'
const config = await ha.dashboard.get('dashboard-test')
config.views[0].title = 'New Title'
await ha.dashboard.save('dashboard-test', config)
ha.close()
```

### Get automation config, mutate, and save back
```js
import ha from './api/index.js'
const { id } = (await ha.automations.listSummary())[0]
const auto = await ha.automations.get(id)
auto.alias = 'Renamed'
await ha.automations.update(id, auto)
ha.close()
```

---

## Documentation Snapshots

After any change, update the local docs to reflect the new state. These files are the source of truth for future sessions.

### Local doc files

| File | What it tracks | When to update |
|------|---------------|----------------|
| `ha/device-inventory.md` | All devices, entity IDs, switch mappings, sync automations | After adding/renaming a device, entity, area, or automation |
| `ha/dashboard-mobile.json` | Current mobile dashboard config | After every `dashboard.save('dashboard-mobile', ...)` |
| `ha/dashboard-patylherme-home.json` | Paty+Gui shared dashboard | After every `dashboard.save('dashboard-patylherme-home', ...)` |
| `ha/dashboard-e-ink.json` / `ha/eink-dashboard.json` | E-ink dashboard | After every e-ink dashboard change |
| `ha/dashboard-test.json` | Test/dev dashboard (create if missing) | After every `dashboard.save('dashboard-test', ...)` |

---

### After an Automation change

1. **Apply** the change via the API
2. **Verify** it in HA (see Validation Workflow below)
3. **Update `device-inventory.md`** — find the relevant automation in the "Sync Automations" section and update the alias, triggers, or actions to match

```bash
# Dump current automation state to review what changed
node -e "
import('./api/index.js').then(async m => {
  const ha = m.default
  const summary = await ha.automations.listSummary()
  summary.forEach(a => console.log(a.id, '|', a.name))
  ha.close()
})"
# Then manually update device-inventory.md to match
```

---

### After a Dashboard change

Always save the updated config back to the local JSON file immediately after `dashboard.save()`:

```js
// In your script — save to API AND to local file in one step
import ha from './api/index.js'
import { writeFile } from 'fs/promises'

const urlPath = 'dashboard-mobile'
const config = /* your updated config */

await ha.dashboard.save(urlPath, config)
await writeFile(`../${urlPath}.json`, JSON.stringify(config, null, 2))

ha.close()
```

Or if you made changes via the HA UI and want to pull them back to local:

```bash
node -e "
import('./api/index.js').then(async m => {
  const ha = m.default
  const { writeFile } = await import('fs/promises')

  for (const urlPath of ['dashboard-mobile', 'dashboard-patylherme-home', 'dashboard-test']) {
    try {
      const config = await ha.dashboard.get(urlPath)
      await writeFile(\`../\${urlPath}.json\`, JSON.stringify(config, null, 2))
      console.log('Saved:', urlPath + '.json')
    } catch(e) {
      console.log('Skipped:', urlPath, '-', e.message)
    }
  }
  ha.close()
})"
```

---

### After a Device / Entity Registry change

Update `device-inventory.md` to reflect the new name or area assignment:

1. Find the device's section in `device-inventory.md`
2. Update the `Entity ID`, device name, or area header
3. If the area changed, move the device row to the correct area section
4. If switch mappings changed, update the corresponding switch table

---

## Validation Workflow

After any change via the API, always verify it worked in the HA UI using agent-browser.

### 0. Setup — open HA (once per session)

```bash
# Close any leftover session
agent-browser close

# Open HA and inject stored session from ha-auth.json
agent-browser open http://homeassistant.local:8123
```

Then inject the localStorage session so you're logged in:

```bash
agent-browser eval --stdin <<'EVALEOF'
const ls = /* paste output of: node -e "import('./api/auth.js').then(m => console.log(JSON.stringify(Object.fromEntries(require('fs').readFileSync('../ha-auth.json','utf8') ... ))))" */
Object.entries(ls).forEach(([k, v]) => localStorage.setItem(k, v))
'session injected'
EVALEOF

agent-browser open http://homeassistant.local:8123
agent-browser wait --load networkidle
```

> **Shortcut:** use the `ha-session` helper below to inject in one step.

---

### 1. After creating or updating an Automation

```bash
# Navigate to the Automations page
agent-browser open http://homeassistant.local:8123/config/automation/dashboard
agent-browser wait --load networkidle

# Take an annotated screenshot to see the list
agent-browser screenshot --annotate

# Confirm the automation name appears in the list
agent-browser snapshot -i
# Look for the automation alias in the output

# Optional: open the automation to inspect its config
# Click the automation row ref from the snapshot
agent-browser click @<automation-row-ref>
agent-browser wait --load networkidle
agent-browser screenshot --annotate
```

**What to check:**
- Automation appears in the list with the correct name
- State is `on` (enabled)
- If you updated triggers/actions: open it and verify the config visually

---

### 2. After saving a Dashboard

```bash
# Navigate to the dashboard url_path
agent-browser open http://homeassistant.local:8123/dashboard-test/home
agent-browser wait --load networkidle
agent-browser screenshot --annotate

# If the dashboard renders incorrectly (blank/error), check the console
agent-browser eval 'document.querySelector("hui-error-card, .error")?.innerText || "no errors"'
```

**What to check:**
- Dashboard loads without error cards
- Views/cards match what was saved
- Title or layout changes are reflected

---

### 3. After updating Device / Entity Registry

```bash
# Navigate to the device page in HA Settings
agent-browser open http://homeassistant.local:8123/config/devices/dashboard
agent-browser wait --load networkidle

# Search for the device by name
agent-browser snapshot -i
# Find the search input ref and type the device name
agent-browser fill @<search-ref> "Device Name"
agent-browser wait 1000
agent-browser screenshot --annotate
```

Or verify via the API itself (no browser needed for this):

```bash
node -e "
import('./api/index.js').then(async m => {
  const ha = m.default
  const devices = await ha.registry.listDevices()
  const d = devices.find(d => d.name === 'Expected Name')
  console.log('Found:', d?.name, '| Area:', d?.area_id)
  ha.close()
})"
```

**What to check:**
- Device shows new name
- Device is assigned to the correct area
- Entity `friendly_name` updated if expected

---

### 4. Trigger an Automation manually to test it

```bash
# Via HA UI — navigate to the automation and hit "Run"
agent-browser open http://homeassistant.local:8123/config/automation/dashboard
agent-browser wait --load networkidle
agent-browser snapshot -i
# Find the automation row and its run/trigger button
agent-browser click @<run-button-ref>
agent-browser wait 2000
agent-browser screenshot --annotate
```

Or trigger via REST API (no browser needed):

```bash
node -e "
import('./api/auth.js').then(async m => {
  const token = await m.getToken()
  const url = m.getUrl()
  const entityId = 'automation.sincronizar_luminaria_e_interruptor_escritorio_gui'
  const res = await fetch(\`\${url}/api/services/automation/trigger\`, {
    method: 'POST',
    headers: { Authorization: \`Bearer \${token}\`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_id: entityId })
  })
  console.log('Trigger status:', res.status)
})"
```

---

### 5. If something looks wrong — reload HA

Sometimes HA needs a config reload after automation changes:

```bash
node -e "
import('./api/auth.js').then(async m => {
  const token = await m.getToken()
  const url = m.getUrl()
  // Reload automation config without restarting HA
  const res = await fetch(\`\${url}/api/services/automation/reload\`, {
    method: 'POST',
    headers: { Authorization: \`Bearer \${token}\` }
  })
  console.log('Reload status:', res.status)
})"
```

---

## File Structure

```
ha/api/
  index.js       ← HAClient singleton (default export: ha)
  auth.js        ← getToken(), setConfig(), getUrl()
  automations.js ← list, listSummary, get, update, create
  dashboard.js   ← get, save (both WebSocket)
  registry.js    ← listAreas, listDevices, updateDevice, listEntities
  websocket.js   ← sendCommand(type, payload), close()
  package.json   ← { type: module, deps: ws }
```
