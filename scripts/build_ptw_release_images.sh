#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: $0 RELEASE_TAG OUTPUT_DIRECTORY" >&2
    exit 2
fi

release_tag=$1
output_directory=$2
case "$release_tag" in
    *[!A-Za-z0-9._-]*|'') echo "invalid release tag" >&2; exit 2 ;;
esac

mkdir -p "$output_directory"

docker buildx build --platform linux/amd64 --load \
    --tag "ptw-commander:$release_tag" \
    --file commander/Dockerfile .
docker save --output "$output_directory/commander.tar" "ptw-commander:$release_tag"

docker buildx build --platform linux/amd64 --load \
    --tag "ptw-validation:$release_tag" \
    --file validation_pipeline/Dockerfile .
docker save --output "$output_directory/validation.tar" "ptw-validation:$release_tag"

docker buildx build --platform linux/amd64 --load \
    --tag "ptw-owner-gateway:$release_tag" \
    --file owner_gateway/Dockerfile .
docker save --output "$output_directory/owner-gateway.tar" "ptw-owner-gateway:$release_tag"

if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$output_directory/commander.tar" \
        "$output_directory/validation.tar" \
        "$output_directory/owner-gateway.tar" \
        > "$output_directory/SHA256SUMS"
else
    shasum -a 256 "$output_directory/commander.tar" \
        "$output_directory/validation.tar" \
        "$output_directory/owner-gateway.tar" \
        > "$output_directory/SHA256SUMS"
fi

echo "Built Linux/amd64 PTW release $release_tag in $output_directory"
