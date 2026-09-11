#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 RELEASE_TAG PTW_GIT_REVISION PLATFORM_GIT_REVISION" >&2
    exit 2
fi
release_tag=$1
git_revision=$2
platform_git_revision=$3
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || exit 2
[[ $git_revision =~ ^[0-9a-f]{40}$ && $platform_git_revision =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ $(id -u) -eq 0 ]] || { echo "release receiver must run as root" >&2; exit 1; }
[[ ${PTW_MAINTENANCE_LOCK_HELD:-0} == 1 && -e /proc/self/fd/9 ]] || {
    echo "release receiver requires the inherited maintenance lock" >&2; exit 73;
}

repository=/root/ptw
platform=/opt/ptw/platform
[[ $(git -C "$repository" rev-parse HEAD) == "$git_revision" ]] || {
    echo "production PTW checkout is not at the requested revision" >&2; exit 1;
}
deployed_git_revision=""
if [[ -s $repository/.local/deployed-revision ]]; then
    read -r deployed_git_revision < "$repository/.local/deployed-revision"
fi
if [[ ! $deployed_git_revision =~ ^[0-9a-f]{40}$ ]]; then
    deployed_image=$(docker inspect ptw-validation-validation-api-1 --format '{{.Config.Image}}')
    deployed_tag=${deployed_image#ptw-validation:}
    deployed_short_revision=${deployed_tag##*-}
    deployed_git_revision=$(git -C "$repository" rev-parse "$deployed_short_revision^{commit}")
fi
[[ $deployed_git_revision =~ ^[0-9a-f]{40}$ ]] || {
    echo "could not determine the last successful PTW revision" >&2; exit 1;
}
release_directory=$(mktemp -d /var/tmp/ptw-preserving.XXXXXX)
cleanup() { rm -rf -- "$release_directory"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

IFS= read -r stream_version
[[ $stream_version == "PTW-PRESERVING-STREAM 1" ]] || {
    echo "unsupported preserving release stream" >&2; exit 1;
}

receive_artifact() {
    local expected_kind=$1 stream_name=$2 expected_image=${3:-} expected_revision=${4:-}
    local header kind name blocks size digest artifact checksum actual architecture revision_label
    IFS= read -r header
    if [[ $header == "REUSE $stream_name" ]]; then
        printf -v "received_${stream_name//-/_}" '%s' reuse
        return 0
    fi
    if [[ $header == "PRESENT $stream_name" ]]; then
        [[ $expected_kind == IMAGE && -n $expected_image && -n $expected_revision ]] || {
            echo "invalid PRESENT record for $stream_name" >&2; exit 1;
        }
        architecture=$(docker image inspect "$expected_image" --format '{{.Architecture}}')
        revision_label=$(docker image inspect "$expected_image" \
            --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')
        [[ $architecture == amd64 && $revision_label == "$expected_revision" ]] || {
            echo "cached candidate $expected_image does not match the release" >&2; exit 1;
        }
        printf -v "received_${stream_name//-/_}" '%s' present
        return 0
    fi
    read -r kind name blocks size digest <<< "$header"
    [[ $kind == "$expected_kind" && $name == "$stream_name" && $blocks =~ ^[1-9][0-9]*$ \
       && $size =~ ^[1-9][0-9]*$ && $digest =~ ^[0-9a-f]{64}$ ]] || {
        echo "invalid release stream header for $stream_name" >&2; exit 1;
    }
    (( size <= blocks * 1048576 && size > (blocks - 1) * 1048576 )) || {
        echo "invalid release artifact size for $stream_name" >&2; exit 1;
    }
    artifact="$release_directory/$stream_name"
    dd iflag=fullblock bs=1048576 count="$blocks" of="$artifact" status=none
    IFS= read -r header
    [[ -z $header ]] || { echo "invalid release stream separator" >&2; exit 1; }
    truncate --size "$size" "$artifact"
    checksum=$(sha256sum "$artifact"); actual=${checksum%% *}
    [[ $actual == "$digest" ]] || { echo "checksum mismatch for $stream_name" >&2; exit 1; }
    if [[ $expected_kind == IMAGE ]]; then
        docker load --input "$artifact" >/dev/null
        architecture=$(docker image inspect "$expected_image" --format '{{.Architecture}}')
        [[ $architecture == amd64 ]] || { echo "$expected_image is not linux/amd64" >&2; exit 1; }
        if [[ -n $expected_revision ]]; then
            revision_label=$(docker image inspect "$expected_image" \
                --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')
            [[ $revision_label == "$expected_revision" ]] || {
                echo "$expected_image revision label does not match the release" >&2; exit 1;
            }
        fi
    fi
    printf -v "received_${stream_name//-/_}" '%s' published
}

receive_artifact IMAGE commander "ptw-commander:$release_tag" "$git_revision"
receive_artifact IMAGE validation "ptw-validation:$release_tag" "$git_revision"
receive_artifact IMAGE owner-gateway "ptw-owner-gateway:$release_tag" "$git_revision"
receive_artifact IMAGE commander-god "ptw-commander-god:$release_tag" "$git_revision"
receive_artifact IMAGE platform-commander-api "ptw-agent-platform-commander-api:$release_tag" "$platform_git_revision"
receive_artifact IMAGE platform-commander-worker "ptw-agent-platform-commander-worker:$release_tag" "$platform_git_revision"
receive_artifact IMAGE platform-codex-auth "ptw-agent-platform-codex-auth:$release_tag" "$platform_git_revision"
receive_artifact FILE platform-revision
receive_artifact FILE release-plan
IFS= read -r stream_end
[[ $stream_end == END ]] || { echo "release stream did not terminate cleanly" >&2; exit 1; }

plan="$release_directory/release-plan"
[[ $received_release_plan == published ]]
python3 "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/plan_ptw_release.py" --validate "$plan" \
    --target "$git_revision" --release-tag "$release_tag" >/dev/null
planned_base=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["base_revision"])' "$plan")
plan_mode=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mode"])' "$plan")
[[ $plan_mode != selective || $planned_base == "$deployed_git_revision" ]] || {
    echo "release plan base does not match the deployed PTW revision" >&2; exit 1;
}
plan_value() {
    python3 - "$plan" "$1" "$2" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]][sys.argv[3]]
print("1" if value else "0")
PY
}

image_components=()
restart_components=()
for component in commander validation owner-gateway commander-god; do
    variable=received_${component//-/_}
    received=${!variable}
    planned=$(plan_value build "$component")
    [[ ($planned == 1 && ($received == published || $received == present)) \
       || ($planned == 0 && $received == reuse) ]] || {
        echo "release stream does not match the $component plan" >&2; exit 1;
    }
    [[ $planned == 0 ]] || image_components+=("$component")
    [[ $(plan_value restart "$component") == 0 ]] || restart_components+=("$component")
done
has_migrations=$(python3 - "$plan" <<'PY'
import json, sys
print("1" if json.load(open(sys.argv[1], encoding="utf-8"))["migrations"] else "0")
PY
)
[[ $has_migrations != 1 || ${PTW_MIGRATIONS_AUTHORIZED:-0} == 1 ]] || {
    echo "migration-bearing releases require the backup-bearing in-place path" >&2; exit 1;
}

platform_states="$received_platform_commander_api $received_platform_commander_worker $received_platform_codex_auth"
if [[ $platform_states == "reuse reuse reuse" ]]; then
    [[ $received_platform_revision == reuse ]] || { echo "unexpected platform revision bundle" >&2; exit 1; }
    [[ $(git -C "$platform" rev-parse HEAD) == "$platform_git_revision" ]] || {
        echo "platform images were reused but the deployed revision differs" >&2; exit 1;
    }
elif [[ $received_platform_commander_api =~ ^(published|present)$ \
     && $received_platform_commander_worker =~ ^(published|present)$ \
     && $received_platform_codex_auth =~ ^(published|present)$ ]]; then
    [[ $received_platform_revision == published ]] || { echo "changed platform requires a revision bundle" >&2; exit 1; }
    git -C "$platform" bundle verify "$release_directory/platform-revision" >/dev/null
    git -C "$platform" fetch "$release_directory/platform-revision" HEAD
    [[ $(git -C "$platform" rev-parse FETCH_HEAD) == "$platform_git_revision" ]] || {
        echo "platform revision bundle does not match the requested commit" >&2; exit 1;
    }
    git -C "$platform" merge --ff-only "$platform_git_revision"
    image_components+=(platform)
    restart_components+=(platform)
else
    echo "platform services must be reused or published together" >&2
    exit 1
fi

join_components() { local IFS=,; printf '%s' "$*"; }
export PTW_RELEASE_IMAGE_COMPONENTS="$(join_components "${image_components[@]}")"
export PTW_RELEASE_RESTART_COMPONENTS="$(join_components "${restart_components[@]}")"
"${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/deploy_ptw_selective.sh" \
    "$release_tag" "$git_revision" "$platform_git_revision"
