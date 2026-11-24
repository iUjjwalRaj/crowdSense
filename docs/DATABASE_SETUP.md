# Database Setup

## Local SQLite

No external database is required for local persistence. The default database is created at:

```text
.crowdsense/crowdsense.db
```

Override it with:

```sh
export CROWDSENSE_DATABASE_URL="sqlite:///./crowdsense.db"
export CROWDSENSE_DATA_DIR=".crowdsense"
```

Tables are created automatically at application startup with SQLAlchemy metadata.
This is schema bootstrapping, not a substitute for versioned migration history.

## PostgreSQL

Before production use:

1. Provision PostgreSQL and configure `CROWDSENSE_DATABASE_URL`.
2. Install a PostgreSQL SQLAlchemy driver.
3. Create the database and application role.
4. Restrict the role to the required schema privileges.
5. Run startup migration/schema creation.

The PostgreSQL driver is not installed by this repository and must not be fabricated.

## Health

`GET /api/v1/health/readiness` includes database health:

- `healthy: true` when `SELECT 1` succeeds
- `healthy: false` with a non-secret blocking error class

Startup failures are logged without exposing database credentials. The application does
not print database URLs or passwords.

## Restart verification

Persistence tests create a fresh SQLite database, write records, reopen a new engine,
and verify that records survive the simulated restart. Duplicate route imports update
the existing unique route rather than inserting a second row.
