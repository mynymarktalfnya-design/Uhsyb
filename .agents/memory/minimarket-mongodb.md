---
name: MiniMarket MongoDB setup
description: MongoDB Atlas must be reachable from Replit; mongomock fallback is dev-only
---

The secure MONGO_URL secret now points to an Atlas cluster, but the current connection attempt fails during TLS negotiation; verify Atlas Network Access allows Replit before treating it as production-ready.
`database.py` tries a real ping; if it fails and `ALLOW_MONGOMOCK=true` is set, it falls back to in-memory mongomock (data lost on restart).

**Why:** ALLOW_MONGOMOCK must be explicit so production misconfigurations don't silently lose data.

**How to apply:** Keep `ALLOW_MONGOMOCK=true` only in development. Production is configured with `ALLOW_MONGOMOCK=false`; after Atlas Network Access and credentials are valid, `/api/health` must report `persistent=true`.
