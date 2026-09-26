#!/bin/sh
set -eu

escaped_password=$(printf '%s' "$KEYCLOAK_DATABASE_PASSWORD" | sed "s/'/''/g")
psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE USER keycloak WITH PASSWORD '$escaped_password';
CREATE DATABASE keycloak OWNER keycloak;
REVOKE ALL ON DATABASE keycloak FROM PUBLIC;
SQL
