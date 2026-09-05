---
name: MiniMarket database setup
description: Neon PostgreSQL is the active persistent store; MongoDB is legacy fallback only
---

Neon PostgreSQL is selected whenever the secure `NEON_DATABASE_URL` secret exists. The application keeps its existing document-shaped route API while persisting documents in a JSONB table; MongoDB and mongomock remain legacy fallback paths.

**Why:** ALLOW_MONGOMOCK must be explicit so production misconfigurations don't silently lose data.

**How to apply:** Keep `ALLOW_MONGOMOCK=true` only in development. Production is configured with `ALLOW_MONGOMOCK=false`; verify `/api/health` reports `db=neon-postgres` and `persistent=true` after deployment.
