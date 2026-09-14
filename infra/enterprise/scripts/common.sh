#!/bin/sh
# POSIX shell + Docker CLI/Compose v2 + GNU coreutils; no host language runtime.
set -eu
umask 077
fail() { printf '{"status":"FAIL","code":"%s"}\n' "$1" >&2; exit 1; }
[ "$#" -ge 8 ] || fail ARGUMENTS_REQUIRED
ACTION=$1 BUNDLE=$2 PACKAGE_SHA=$3 IMAGE=$4 SLOT=$5 PROJECT=$6 PORT=$7 MODE=$8
shift 8
PG='postgres:17.6-alpine3.22@sha256:ef257d85f76e48da1c64832459b59fcaba1a4dac97bf5d7450c77753542eee94'
REDIS='redis:8.2.1-alpine3.22@sha256:987c376c727652f99625c7d205a1cba3cb2c53b92b0b62aade2bd48ee1593232'
for tool in docker sha256sum awk find df mktemp realpath cmp cp mv mkdir chmod rm rmdir dirname uname; do
    command -v "$tool" >/dev/null 2>&1 || fail SYSTEM_TOOL_MISSING
done
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] || fail LINUX_AMD64_REQUIRED
case "$ACTION" in preflight|install|start|status|logs|stop|backup|restore|rollback) ;; *) fail ACTION_INVALID;; esac
case "$PROJECT" in ''|*[!a-z0-9-]*|[!a-z]*) fail PROJECT_INVALID;; esac
[ "${#PROJECT}" -ge 2 ] && [ "${#PROJECT}" -le 48 ] || fail PROJECT_INVALID
case "$IMAGE" in sha256:*) ;; *) fail IMAGE_ID_REQUIRED;; esac
[ "${#IMAGE}" -eq 71 ] || fail IMAGE_ID_REQUIRED
case "${IMAGE#sha256:}" in *[!0-9a-f]*) fail IMAGE_ID_REQUIRED;; esac
case "$MODE" in standalone|enterprise) ;; *) fail MODE_INVALID;; esac
safe_directory() {
    case "$1" in /*) ;; *) fail ABSOLUTE_PATH_REQUIRED;; esac
    case "$1" in /|*[!A-Za-z0-9_./-]*) fail PATH_INVALID;; esac
    [ -d "$1" ] && [ "$(realpath -e "$1")" = "$1" ] || fail DIRECTORY_INVALID
    path_check=$1
    while [ "$path_check" != / ]; do
        [ ! -L "$path_check" ] || fail SYMLINK_REFUSED
        path_check=${path_check%/*}; [ -n "$path_check" ] || path_check=/
    done
    scan=$(find "$1" -type l -print -quit 2>/dev/null) || fail DIRECTORY_UNREADABLE
    [ -z "$scan" ] || fail SYMLINK_REFUSED
    scan=$(find "$1" ! -type d ! -type f -print -quit 2>/dev/null) || fail DIRECTORY_UNREADABLE
    [ -z "$scan" ] || fail NONREGULAR_INPUT_REFUSED
}
verify_files() {
    safe_directory "$1"
    [ "${#2}" -eq 64 ] || fail CHECKSUM_REQUIRED
    case "$2" in *[!0-9a-f]*) fail CHECKSUM_REQUIRED;; esac
    [ -f "$1/SHA256SUMS" ] || fail CHECKSUM_REQUIRED
    actual=$(sha256sum "$1/SHA256SUMS"); actual=${actual%% *}
    [ "$actual" = "$2" ] || fail MANIFEST_CHECKSUM_MISMATCH
    # Restrict checksum paths before passing them to sha256sum; reject traversal,
    # duplicate entries and nonregular payloads. Manifest authenticity is external.
    awk 'NF != 2 || length($1) != 64 || $1 ~ /[^0-9a-f]/ || $2 !~ /^[A-Za-z0-9_-][A-Za-z0-9_.\/-]*$/ || $2 ~ /(^|\/)\.\.?($|\/)/ || seen[$2]++ {bad=1} END {exit bad || NR==0}' "$1/SHA256SUMS" || fail MANIFEST_INVALID
    (cd "$1" && sha256sum --strict --status -c SHA256SUMS 2>/dev/null) || fail PAYLOAD_CHECKSUM_MISMATCH
}
safe_directory "$SLOT"
safe_directory "$SLOT/config"
safe_directory "$SLOT/secrets"
verify_files "$BUNDLE" "$PACKAGE_SHA"
LAYOUT=legacy
SCRIPTS=infra/enterprise/scripts BOOTSTRAP=infra/enterprise/bootstrap COMPOSE=infra/enterprise/compose
ARCHIVE=image.tar REPORT=image-report.json
if [ -f "$BUNDLE/MANIFEST.json" ]; then
    LAYOUT=offline
    SCRIPTS=scripts BOOTSTRAP=scripts/bootstrap COMPOSE=compose
    ARCHIVE=images/runtime.tar REPORT=evidence/image-report.json
    # This non-executable mapping is already covered by the external checksum.
    awk 'NF!=2 || $1 !~ /^(runtime|database|redis)$/ || length($2)!=71 || substr($2,1,7)!="sha256:" || substr($2,8) ~ /[^0-9a-f]/ || seen[$1]++ {bad=1} END {exit bad || NR!=3}' "$BUNDLE/images/identities.tsv" || fail IMAGE_MAPPING_INVALID
    mapped=$(awk '$1=="runtime" {print $2}' "$BUNDLE/images/identities.tsv")
    [ "$mapped" = "$IMAGE" ] || fail IMAGE_MAPPING_INVALID
    PG=$(awk '$1=="database" {print $2}' "$BUNDLE/images/identities.tsv")
    REDIS=$(awk '$1=="redis" {print $2}' "$BUNDLE/images/identities.tsv")
fi
case "$0" in "$BUNDLE/$SCRIPTS/common.sh") ;; *) fail EXECUTABLE_OUTSIDE_BUNDLE;; esac
for required in "$ARCHIVE" "$REPORT" "$COMPOSE/docker-compose.enterprise.yml" "$COMPOSE/docker-compose.standalone.yml" "$COMPOSE/dependencies.v1.json" "$COMPOSE/redis-entrypoint.sh" "$COMPOSE/control.py" "$SCRIPTS/metadata.py" "$SCRIPTS/common.sh"; do
    awk -v p="$required" '$2==p {found=1} END {exit !found}' "$BUNDLE/SHA256SUMS" || fail PAYLOAD_UNBOUND
done
find "$BUNDLE" -type f ! -path "$BUNDLE/SHA256SUMS" | while IFS= read -r required; do
    relative=${required#"$BUNDLE"/}
    awk -v p="$relative" '$2==p {found=1} END {exit !found}' "$BUNDLE/SHA256SUMS" || fail PAYLOAD_UNBOUND
done
for required in "$BUNDLE"/"$BOOTSTRAP"/*.py "$BUNDLE"/"$SCRIPTS"/*.sh; do
    relative=${required#"$BUNDLE"/}
    awk -v p="$relative" '$2==p {found=1} END {exit !found}' "$BUNDLE/SHA256SUMS" || fail PAYLOAD_UNBOUND
done
version=$(docker version --format '{{.Server.Version}} {{.Server.Os}} {{.Server.Arch}}' 2>/dev/null) || fail DOCKER_UNAVAILABLE
printf '%s\n' "$version" | awk '$1+0>=27 && $2=="linux" && $3=="amd64" {ok=1} END {exit !ok}' || fail DOCKER_VERSION_UNSUPPORTED
version=$(docker compose version --short 2>/dev/null) || fail COMPOSE_UNAVAILABLE
printf '%s\n' "$version" | awk -F. '{gsub(/^v/,"",$1); if ($1>2 || ($1==2 && $2>=30)) ok=1} END {exit !ok}' || fail COMPOSE_VERSION_UNSUPPORTED
available=$(df -Pk "$SLOT" | awk 'END {print $4}')
[ "$available" -ge 1048576 ] || fail INSUFFICIENT_DISK
[ -w "$SLOT" ] || fail SLOT_NOT_WRITABLE
LOCK="$SLOT/.operations-lock-$PROJECT"
mkdir "$LOCK" 2>/dev/null || fail OPERATION_ALREADY_LOCKED
STATE=$(mktemp -d "$SLOT/.operations-XXXXXX")
MUTATING=0
DOCKER_LOCK=0
cleanup() {
    result=$?
    if [ "$result" -ne 0 ] && [ "$MUTATING" -eq 1 ]; then
        compose stop api worker >/dev/null 2>&1 || :
    fi
    # STATE is the exact mktemp child, never a caller-computed recursive target.
    rm -rf -- "$STATE"
    rmdir "$LOCK"
    if [ "$DOCKER_LOCK" -eq 1 ]; then docker rm "$PROJECT-operations-lock" >/dev/null 2>&1 || :; fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    [ "$ACTION" = install ] || fail LOCAL_IMAGE_UNAVAILABLE
    docker load --input "$BUNDLE/$ARCHIVE" >/dev/null 2>&1 || fail IMAGE_LOAD_FAILED
fi
if [ "$LAYOUT" = offline ]; then
    docker image inspect "$IMAGE" >"$STATE/images.json" 2>/dev/null || fail LOCAL_IMAGE_UNAVAILABLE
else
    docker image inspect "$IMAGE" "$PG" "$REDIS" >"$STATE/images.json" 2>/dev/null || fail LOCAL_IMAGE_UNAVAILABLE
fi
helper() {
    docker run --rm -i --pull never --network none --read-only --user 0:0 \
        --cap-drop ALL --cap-add DAC_READ_SEARCH --security-opt no-new-privileges:true \
        --mount "type=bind,src=$BUNDLE,dst=/delivery,readonly" \
        --mount "type=bind,src=$BUNDLE/$BOOTSTRAP,dst=/opt/enterprise/bootstrap,readonly" \
        --mount "type=bind,src=$SLOT/config,dst=/etc/plantnexus,readonly" \
        --mount "type=bind,src=$SLOT/secrets,dst=/run/secrets,readonly" \
        --mount "type=bind,src=$STATE,dst=/state,readonly" \
        --mount "type=bind,src=$BACKUP_MOUNT,dst=/backup,readonly" \
        --workdir /opt/enterprise --entrypoint python "$IMAGE" \
        /delivery/$SCRIPTS/metadata.py "$@"
}
BACKUP_MOUNT=$STATE
helper environment "$BUNDLE" "$SLOT" "$PROJECT" "$PORT" "$MODE" "$IMAGE" <"$STATE/images.json" >"$STATE/compose.env" 2>/dev/null || fail CONFIGURATION_PREFLIGHT_FAILED
if [ "$LAYOUT" = offline ]; then
    # Configuration and package identity have passed before importing dependencies.
    for role in database redis; do
        expected=$(awk -v r="$role" '$1==r {print $2}' "$BUNDLE/images/identities.tsv")
        if ! docker image inspect "$expected" >/dev/null 2>&1; then
            if [ "$ACTION" = preflight ]; then continue; fi
            [ "$ACTION" = install ] || fail LOCAL_DEPENDENCY_UNAVAILABLE
            docker load --input "$BUNDLE/images/$role.tar" >/dev/null 2>&1 || fail DEPENDENCY_LOAD_FAILED
        fi
        actual=$(docker image inspect --format '{{.Id}} {{.Os}}/{{.Architecture}}' "$expected" 2>/dev/null) || fail LOCAL_DEPENDENCY_UNAVAILABLE
        [ "$actual" = "$expected linux/amd64" ] || fail DEPENDENCY_IDENTITY_MISMATCH
    done
fi
docker create --name "$PROJECT-operations-lock" --pull never --network none --read-only --cap-drop ALL --entrypoint /bin/true "$IMAGE" >/dev/null 2>&1 || fail PROJECT_OPERATION_LOCKED
DOCKER_LOCK=1
# Compose interpolation must use the explicit verified file, not ambient overrides.
unset RUNTIME_IMAGE_ID CONFIG_DIR SECRETS_DIR CPU_LIMIT MEMORY_MIB DB_NAME API_HOST_PORT RUNTIME_NETWORK ISOLATED_NETWORK COMPOSE_FILE COMPOSE_PROFILES COMPOSE_PROJECT_NAME COMPOSE_ENV_FILES
compose() {
    if [ "$MODE" = standalone ]; then
        docker compose --project-name "$PROJECT" --env-file "$STATE/compose.env" -f "$BUNDLE/$COMPOSE/docker-compose.enterprise.yml" -f "$BUNDLE/$COMPOSE/docker-compose.standalone.yml" "$@"
    else
        docker compose --project-name "$PROJECT" --env-file "$STATE/compose.env" -f "$BUNDLE/$COMPOSE/docker-compose.enterprise.yml" "$@"
    fi
}
quiet() { "$@" >/dev/null 2>&1 || fail OPERATION_FAILED; }
capture_identity() {
    quiet compose exec -T api python -m bootstrap.services health-api
    quiet compose exec -T worker python -m bootstrap.services health-worker
    for role in api worker; do
        cid=$(compose ps -q "$role" 2>/dev/null) || fail PROCESS_MISSING
        actual=$(docker inspect --format '{{.Image}}' "$cid" 2>/dev/null) || fail PROCESS_MISSING
        [ "$actual" = "$IMAGE" ] || fail PROCESS_IMAGE_MISMATCH
        compose exec -T "$role" cat /tmp/runtime-descriptor.json >"$STATE/$role.json" 2>/dev/null || fail IDENTITY_UNAVAILABLE
        chmod 644 "$STATE/$role.json"
    done
    helper receipt "$IMAGE" >"$STATE/identity.json" 2>/dev/null || fail IDENTITY_MISMATCH
}
check_existing_target() {
    ids=$(compose ps -a -q 2>/dev/null) || fail TARGET_INSPECTION_FAILED
    for cid in $ids; do
        role=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.service"}}' "$cid" 2>/dev/null) || fail TARGET_INSPECTION_FAILED
        actual=$(docker inspect --format '{{.Config.Image}}' "$cid" 2>/dev/null) || fail TARGET_INSPECTION_FAILED
        case "$role" in
            api|worker|migrate|validator) [ "$actual" = "$IMAGE" ] || fail EXISTING_IMAGE_MISMATCH;;
            database) [ "$MODE" = standalone ] && [ "$actual" = "$PG" ] || fail EXISTING_IMAGE_MISMATCH;;
            redis) [ "$MODE" = standalone ] && [ "$actual" = "$REDIS" ] || fail EXISTING_IMAGE_MISMATCH;;
            *) fail EXISTING_SERVICE_MISMATCH;;
        esac
    done
}
start_runtime() {
    MUTATING=1
    quiet compose stop api worker
    if [ "$MODE" = standalone ]; then
        quiet compose up -d --wait --wait-timeout 90 database redis
    fi
    quiet compose run --rm --no-deps migrate
    # Always recreate the exact Worker after dependencies; no reliance on reconnect.
    quiet compose up -d --no-deps --force-recreate --wait --wait-timeout 150 worker
    quiet compose up -d --no-deps --force-recreate --wait --wait-timeout 150 api
    capture_identity
    cp "$STATE/identity.json" "$SLOT/validated.json"
    MUTATING=0
}
pgclient() {
    docker run --rm -i --pull never --network "$PROJECT-runtime" --read-only \
        --user 10001:10001 --cap-drop ALL --security-opt no-new-privileges:true \
        --mount "type=bind,src=$SLOT/config,dst=/etc/plantnexus,readonly" \
        --mount "type=bind,src=$SLOT/secrets,dst=/run/secrets,readonly" \
        --mount "type=bind,src=$BUNDLE/$SCRIPTS/pg-client.sh,dst=/pg-client.sh,readonly" \
        --entrypoint /bin/sh "$PG" /pg-client.sh "$@"
}
check_existing_target
case "$ACTION" in
    preflight) [ "$#" -eq 0 ] || fail ARGUMENTS_INVALID;;
    install|start) [ "$#" -eq 0 ] || fail ARGUMENTS_INVALID; start_runtime;;
    status)
        [ "$#" -eq 0 ] || fail ARGUMENTS_INVALID
        capture_identity
        cmp -s "$STATE/identity.json" "$SLOT/validated.json" || fail SLOT_CONFIGURATION_DRIFT;;
    logs)
        [ "$#" -eq 0 ] || fail ARGUMENTS_INVALID
        compose logs --no-color --tail 200 api worker >"$STATE/raw-logs" 2>/dev/null || fail LOGS_UNAVAILABLE
        helper logs <"$STATE/raw-logs" || fail LOGS_UNAVAILABLE;;
    stop) [ "$#" -eq 0 ] || fail ARGUMENTS_INVALID; quiet compose stop;;
    backup)
        [ "$#" -eq 2 ] && [ "$2" = "QUIESCE-$PROJECT" ] || fail QUIESCE_CONFIRMATION_REQUIRED
        published=$1
        safe_directory "$(dirname "$published")"
        case "$published" in /*) ;; *) fail ABSOLUTE_PATH_REQUIRED;; esac
        case "$published" in *[!A-Za-z0-9_./-]*|"$SLOT"/*|"$BUNDLE"/*) fail BACKUP_PATH_INVALID;; esac
        [ ! -e "$published" ] || fail BACKUP_ALREADY_EXISTS
        capture_identity
        cmp -s "$STATE/identity.json" "$SLOT/validated.json" || fail SLOT_CONFIGURATION_DRIFT
        MUTATING=1
        quiet compose stop api worker
        quiet pgclient head
        # Atomic publication; failures leave existing data and backups untouched.
        output=$(mktemp -d "$(dirname "$published")/.p826-backup-XXXXXX") || fail BACKUP_DIRECTORY_FAILED
        pgclient dump >"$output/database.dump" 2>/dev/null || fail BACKUP_FAILED
        cp "$STATE/api.json" "$STATE/worker.json" "$output/"
        BACKUP_MOUNT=$output
        # Metadata helper reads only this backup, never receives write access.
        helper metadata "$IMAGE" "$PROJECT" >"$output/metadata.json" 2>/dev/null || fail BACKUP_METADATA_FAILED
        (cd "$output" && sha256sum database.dump api.json worker.json metadata.json >SHA256SUMS)
        mv -T -n "$output" "$published" || fail BACKUP_PUBLICATION_FAILED
        [ ! -e "$output" ] || fail BACKUP_ALREADY_EXISTS
        printf 'backup_manifest_sha256=%s\n' "$(sha256sum "$published/SHA256SUMS" | awk '{print $1}')"
        MUTATING=0;;
    restore|rollback)
        [ "$#" -eq 3 ] && [ "$3" = "TARGET-$PROJECT" ] || fail TARGET_CONFIRMATION_REQUIRED
        BACKUP_MOUNT=$1
        verify_files "$BACKUP_MOUNT" "$2"
        # The restore target may not be the source project, even when empty.
        helper verify-backup "$IMAGE" "$PROJECT" >/dev/null 2>&1 || fail BACKUP_VERIFICATION_FAILED
        if [ "$ACTION" = rollback ]; then
            [ -f "$SLOT/validated.json" ] || fail VALIDATED_SLOT_REQUIRED
            # Compare a previously verified slot receipt to the backed-up identity.
            cp "$BACKUP_MOUNT/api.json" "$STATE/api.json"
            cp "$BACKUP_MOUNT/worker.json" "$STATE/worker.json"
            chmod 644 "$STATE/api.json" "$STATE/worker.json"
            helper receipt "$IMAGE" >"$STATE/expected.json" 2>/dev/null || fail BACKUP_IDENTITY_MISMATCH
            cmp -s "$STATE/expected.json" "$SLOT/validated.json" || fail SLOT_IDENTITY_MISMATCH
        fi
        running=$(compose ps -q 2>/dev/null) || fail TARGET_INSPECTION_FAILED
        [ -z "$running" ] || fail STOPPED_ISOLATED_TARGET_REQUIRED
        MUTATING=1
        if [ "$MODE" = standalone ]; then
            quiet compose up -d --wait --wait-timeout 90 database redis
        fi
        quiet pgclient empty
        quiet compose run --rm --no-deps migrate python -c 'from bootstrap.services import prepare,CONFIG;from redis import Redis;p=prepare(CONFIG);clients=[Redis.from_url(getattr(p.settings,f).get_secret_value(),socket_timeout=3,socket_connect_timeout=3) for f in ("redis_url","celery_broker_url","celery_result_backend_url")];assert all(c.dbsize()==0 for c in clients);[c.close() for c in clients]'
        pgclient restore <"$BACKUP_MOUNT/database.dump" >/dev/null 2>&1 || fail RESTORE_FAILED
        quiet pgclient head
        start_runtime
        MUTATING=1
        helper compare-restored "$IMAGE" "$PROJECT" >/dev/null 2>&1 || fail RESTORED_IDENTITY_MISMATCH
        MUTATING=0;;
esac
printf '{"status":"PASS","action":"%s","production_ready":false}\n' "$ACTION"
