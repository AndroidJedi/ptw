#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: $0 RELEASE_TAG OUTPUT_DIRECTORY" >&2
    exit 2
fi

release_tag=$1
output_directory=$2
case "$release_tag" in
    latest|*[!A-Za-z0-9._-]*|'') echo "invalid or unversioned release tag" >&2; exit 2 ;;
esac

mkdir -p "$output_directory"

docker buildx build --platform linux/amd64 --load \
    --tag "ptw-agent-platform-commander-api:$release_tag" \
    --file commander/Dockerfile .
docker buildx build --platform linux/amd64 --load \
    --tag "ptw-agent-platform-commander-worker:$release_tag" \
    --file worker/Dockerfile .

for image in \
    "ptw-agent-platform-commander-api:$release_tag" \
    "ptw-agent-platform-commander-worker:$release_tag"
do
    architecture=$(docker image inspect "$image" --format '{{.Architecture}}')
    [ "$architecture" = amd64 ] || { echo "$image is not linux/amd64" >&2; exit 1; }
done

docker save --output "$output_directory/commander-api.tar" \
    "ptw-agent-platform-commander-api:$release_tag"
docker save --output "$output_directory/commander-worker.tar" \
    "ptw-agent-platform-commander-worker:$release_tag"

if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$output_directory/commander-api.tar" \
        "$output_directory/commander-worker.tar" > "$output_directory/SHA256SUMS"
else
    shasum -a 256 "$output_directory/commander-api.tar" \
        "$output_directory/commander-worker.tar" > "$output_directory/SHA256SUMS"
fi

echo "Built Linux/amd64 platform bridge release $release_tag in $output_directory"
