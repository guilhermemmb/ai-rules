---
name: rtk
description: AI rules/agent definition for rtk.md
---

# RTK — Rust Token Killer

RTK is a token-optimized CLI proxy. It intercepts dev commands (git, pnpm, etc.)
and filters output to reduce token usage by 60-90%.

**The Claude Code hook rewrites commands transparently.** No manual action
needed — `git status` automatically becomes `rtk git status`.

## Meta Commands (use `rtk` directly)

```bash
rtk gain              # Token savings analytics
rtk gain --history    # Command history with savings
rtk discover          # Find missed optimization opportunities
rtk proxy <cmd>       # Execute raw without filtering (debug)
rtk --version         # Verify installation
```

## Verification

```bash
rtk --version   # Should show: rtk X.Y.Z
which rtk       # Verify binary location
```

Name collision: `rtk gain` failing may mean `reachingforthejack/rtk` (Rust Type
Kit) is installed instead of the correct binary.
