---
name: MiniMarket MongoDB setup
description: MongoDB Atlas reachability is fixed; remaining failures are credential or URI mismatches
---

Atlas Network Access now allows the connection, and the secure MONGO_URL secret is present with no shared-env override. The remaining failure is Atlas authentication, so verify the URI belongs to the active cluster and its username/password match the Atlas Database User.
`database.py` tries a real ping; if it fails and `ALLOW_MONGOMOCK=true` is set, it falls back to in-memory mongomock (data lost on restart).

**Why:** ALLOW_MONGOMOCK must be explicit so production misconfigurations don't silently lose data.

**How to apply:** Keep `ALLOW_MONGOMOCK=true` only in development. Production is configured with `ALLOW_MONGOMOCK=false`; after Atlas Network Access and credentials are valid, `/api/health` must report `persistent=true`.
