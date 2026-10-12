#!/usr/bin/env bash

set -euo pipefail

# shellcheck disable=SC2153 # TAGS is set by the workflow step's env.
read -ra tags <<<"${TAGS}"
for tag in "${tags[@]}"; do
	gh workflow run publish.yml \
		--repo "${GITHUB_REPOSITORY}" \
		--ref "${tag}" \
		-f tag="${tag}"
done
