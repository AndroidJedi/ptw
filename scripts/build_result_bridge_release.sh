#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 RELEASE_TAG OUTPUT_DIRECTORY" >&2
  exit 2
fi
release_tag=$1
output_directory=$2
case "$release_tag" in
  ""|latest|*[!A-Za-z0-9._-]*) echo "invalid release tag" >&2; exit 2 ;;
esac
[ -z "$(git status --porcelain --untracked-files=no)" ] || {
  echo "tracked platform changes must be committed" >&2
  exit 1
}
mkdir -p "$output_directory"

docker buildx build --platform linux/amd64 --load \
  --tag "ptw-agent-platform-commander-api:$release_tag" \
  --file commander/Dockerfile .
docker save --output "$output_directory/commander-api.tar" \
  "ptw-agent-platform-commander-api:$release_tag"

docker buildx build --platform linux/amd64 --load \
  --tag "ptw-agent-platform-commander-worker:$release_tag" \
  --file worker/Dockerfile .
docker save --output "$output_directory/commander-worker.tar" \
  "ptw-agent-platform-commander-worker:$release_tag"

git bundle create "$output_directory/platform-revision.bundle" HEAD
git bundle verify "$output_directory/platform-revision.bundle"
echo "Built Linux/amd64 Result bridge release $release_tag"
