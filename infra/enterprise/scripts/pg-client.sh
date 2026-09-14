#!/bin/sh
# Runs only inside the locked PostgreSQL client image. No credential argv/logs.
set -eu
value() { awk -F= -v key="$1" '$1==key {print substr($0,length(key)+2)}' /etc/plantnexus/deployment.env; }
PGHOST=$(value DB_HOST); PGPORT=$(value DB_PORT); PGDATABASE=$(value DB_NAME)
PGUSER=$(cat "$(value DB_USER_FILE)"); PGPASSWORD=$(cat "$(value DB_PASSWORD_FILE)")
PGCONNECT_TIMEOUT=5
export PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGCONNECT_TIMEOUT
case "$1" in
    head) [ "$(psql -XAtq -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')" = 0009_host_authorization_audit ];;
    empty) [ "$(psql -XAtq -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S','f')")" = 0 ];;
    dump) exec pg_dump --format=custom --no-owner --no-acl;;
    restore) exec pg_restore --exit-on-error --single-transaction --no-owner --no-acl --dbname "$PGDATABASE";;
    *) exit 1;;
esac
