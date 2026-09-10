#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 2 && $# -ne 4 ]] || { [[ $# -eq 4 ]] && [[ $3 != --base-revision ]]; }; then
    echo "usage: $0 RELEASE_TAG OUTPUT_DIRECTORY [--base-revision REVISION]" >&2
    exit 2
fi

release_tag=$1
output_directory=$2
base_revision=${4:-}
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || {
    echo "invalid or unversioned release tag" >&2; exit 2;
}
revision=$(git rev-parse HEAD)
[[ -z $(git status --porcelain) ]] || {
    echo "tracked PTW changes must be committed before building" >&2; exit 1;
}
mkdir -p "$output_directory"
rm -f -- "$output_directory/commander.tar" "$output_directory/validation.tar" \
    "$output_directory/owner-gateway.tar" "$output_directory/commander-god.tar"

plan="$output_directory/release-plan.json"
if [[ -n $base_revision ]]; then
    python3 scripts/plan_ptw_release.py --base "$base_revision" --target "$revision" \
        --release-tag "$release_tag" --output "$plan"
else
    python3 - "$release_tag" "$revision" "$plan" <<'PY'
import json, pathlib, sys
tag, revision, output = sys.argv[1:]
components = {name: True for name in ("commander", "validation", "owner-gateway", "commander-god")}
pathlib.Path(output).write_text(json.dumps({
    "version": 1, "mode": "full", "release_tag": tag, "base_revision": revision,
    "target_revision": revision, "changed_paths": [], "unmapped_paths": [],
    "build": components, "restart": components,
    "hosting": {"owner-console": True, "public-landings": True}, "migrations": False,
}, sort_keys=True, indent=2) + "\n")
PY
fi

plan_value() {
    python3 - "$plan" "$1" "$2" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]][sys.argv[3]]
print("1" if value else "0")
PY
}

declare -a build_pids=()
declare -a build_names=()
build_component() {
    local component=$1 image=$2 dockerfile=$3
    docker buildx build --platform linux/amd64 --load --provenance=false \
        --label "org.opencontainers.image.revision=$revision" \
        --label "com.provethemwrong.component=$component" \
        --tag "$image:$release_tag" --file "$dockerfile" .
}
queue_build() {
    local component=$1 image=$2 dockerfile=$3
    if [[ $(plan_value build "$component") == 1 ]]; then
        echo "Building $component"
        build_component "$component" "$image" "$dockerfile" &
        build_pids+=("$!")
        build_names+=("$component")
    else
        echo "Reusing deployed $component image"
    fi
}

queue_build commander ptw-commander commander/Dockerfile
queue_build validation ptw-validation validation_pipeline/Dockerfile
queue_build owner-gateway ptw-owner-gateway owner_gateway/Dockerfile
queue_build commander-god ptw-commander-god commander_god/Dockerfile

build_failed=0
for index in "${!build_pids[@]}"; do
    if ! wait "${build_pids[$index]}"; then
        echo "${build_names[$index]} image build failed" >&2
        build_failed=1
    fi
done
[[ $build_failed -eq 0 ]] || exit 1

save_component() {
    local component=$1 image=$2 archive=$3 architecture
    [[ $(plan_value build "$component") == 1 ]] || return 0
    architecture=$(docker image inspect "$image:$release_tag" --format '{{.Architecture}}')
    [[ $architecture == amd64 ]] || { echo "$image:$release_tag is not linux/amd64" >&2; return 1; }
    docker save --output "$output_directory/$archive" "$image:$release_tag"
}
save_component commander ptw-commander commander.tar
save_component validation ptw-validation validation.tar
save_component owner-gateway ptw-owner-gateway owner-gateway.tar
save_component commander-god ptw-commander-god commander-god.tar

python3 scripts/plan_ptw_release.py --validate "$plan" --target "$revision" \
    --release-tag "$release_tag" >/dev/null
echo "Prepared selective Linux/amd64 PTW release $release_tag in $output_directory"
