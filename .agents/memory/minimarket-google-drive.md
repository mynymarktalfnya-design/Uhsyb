---
name: MiniMarket Google Drive backups
description: Persistent backup mirroring through the authorized Google Drive connector
---

The backup service keeps a local gzip copy and mirrors each enabled backup to a dedicated Google Drive folder through the Replit connector proxy. The backups page can list those Drive archives and restore a selected archive after confirmation and password verification. OAuth tokens are minted/refreshed by the connector identity flow and must never be stored in the repo.

**Why:** Google Drive is an external account-level service, while local project files can disappear during a project move or restart.

**How to apply:** Keep the connector bound to the environment, keep drive backup enabled, and treat a local success plus a Drive upload status as the two independent backup layers.