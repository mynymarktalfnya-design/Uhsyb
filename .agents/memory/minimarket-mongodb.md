---
name: MiniMarket MongoDB setup
description: MongoDB Atlas must be reachable from Replit; mongomock fallback is dev-only
---

Atlas Network Access now allows the connection, but the current secure MONGO_URL value is rejected with an authentication failure; verify its database username/password match the Atlas Database User before treating it as production-ready.
`database.py` tries a real ping; if it fails and `ALLOW_MONGOMOCK=true` is set, it falls back to in-memory mongomock (data lost on restart).

**Why:** ALLOW_MONGOMOCK must be explicit so production misconfigurations don't silently lose data.

**How to apply:** Keep `ALLOW_MONGOMOCK=true` only in development. Production is configured with `ALLOW_MONGOMOCK=false`; after Atlas Network Access and credentials are valid, `/api/health` must report `persistent=true`.
