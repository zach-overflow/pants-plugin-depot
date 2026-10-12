#!/usr/bin/env bash

set -euo pipefail

if [[ ! "${TAG}" =~ ^([a-z0-9][a-z0-9-]*)-v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
	echo "::error::'${TAG}' is not a <plugin-name>-vMAJOR.MINOR.PATCH release tag - nothing to \
publish. Release tags must be created via the Release workflow."
	exit 1
fi
echo "package=${BASH_REMATCH[1]}" >>"$GITHUB_OUTPUT"
echo "version=${BASH_REMATCH[2]}" >>"$GITHUB_OUTPUT"
