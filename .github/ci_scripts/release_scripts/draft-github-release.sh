#!/usr/bin/env bash

set -euo pipefail

# shellcheck disable=SC2153 # TAGS is set by the workflow step's env.
read -ra tags <<<"${TAGS}"
for tag in "${tags[@]}"; do
	package="${tag%-v*}"
	changelog="provides/${package}/CHANGELOG.md"
	awk -v heading="## [${tag}]" '
		index($0, heading) == 1 { found = 1; next }
		found && /^- - -$/ { exit }
		found { print }
	' "${changelog}" >release-notes.md
	if ! grep -q '[^[:space:]]' release-notes.md; then
		echo "::error::Found no section for ${tag} in ${changelog}."
		exit 1
	fi
	gh release create "${tag}" \
		--title "${package} ${tag##*-v}" \
		--notes-file release-notes.md \
		--verify-tag \
		--draft
	echo "::notice::Tagged $(git rev-parse HEAD) as ${tag} and drafted the GitHub release; \
Publish attaches the wheel and publishes it."
done
