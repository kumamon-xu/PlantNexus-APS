#!/bin/sh
set -eu
# ACL hashes keep passwords out of argv, environment, logs and persisted config.
password_hash=$(printf %s "$(cat /run/secrets/redis_password)" | sha256sum | cut -d ' ' -f 1)
umask 077
printf 'user default on #%s ~* &* +@all\n' "$password_hash" > /tmp/users.acl
exec redis-server --aclfile /tmp/users.acl --appendonly yes --appendfsync always --dir /data --protected-mode yes
