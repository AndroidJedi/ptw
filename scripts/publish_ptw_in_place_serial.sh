#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 6 || $5 != --confirm || $6 != "DEPLOY PTW IN PLACE" ]]; then
    echo "usage: $0 RELEASE_TAG IMAGE_DIRECTORY PLATFORM_GIT_REVISION PLATFORM_IMAGE_DIRECTORY --confirm 'DEPLOY PTW IN PLACE'" >&2
    exit 2
fi

export PTW_IN_PLACE_DEPLOY_ENTRYPOINT=1
exec "$(dirname "$0")/publish_ptw_release_serial.sh" "$@"
