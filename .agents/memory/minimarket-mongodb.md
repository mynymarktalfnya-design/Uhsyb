---
name: MiniMarket database setup
description: Neon PostgreSQL is the active persistent store; MongoDB is legacy fallback only
---

Neon PostgreSQL is intended to be selected whenever the secure `NEON_DATABASE_URL` secret reaches the API process. The application keeps its existing document-shaped route API while persisting documents in a JSONB table; MongoDB and mongomock remain legacy fallback paths. A secret can exist in the workspace while the running API still falls back to mongomock if its workflow environment does not receive it.

**Why:** ALLOW_MONGOMOCK must be explicit so production misconfigurations don't silently lose data.

**How to apply:** Keep `ALLOW_MONGOMOCK=true` only in development. Production is configured with `ALLOW_MONGOMOCK=false`; verify `/api/health` reports `db=neon-postgres` and `persistent=true` after deployment.
