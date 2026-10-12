#!/usr/bin/env bash

set -euo pipefail

mapfile -t tags < <(git tag --points-at HEAD)
if [[ "$(git rev-parse HEAD)" == "${GITHUB_SHA}" || "${#tags[@]}" -eq 0 ]]; then
	echo "::error::cog created no bump commit or no tag on top of ${GITHUB_SHA}."
	exit 1
fi
if [[ -n "${PACKAGE}" ]]; then
	for tag in "${tags[@]}"; do
		if [[ "${tag}" != "${PACKAGE}-v"* ]]; then
			echo "::error::Release is scoped to '${PACKAGE}' but HEAD carries the tag '${tag}'. Nothing was pushed."
			exit 1
		fi
	done
fi
git push --atomic origin "HEAD:${GITHUB_REF_NAME}" "${tags[@]}"
echo "tags=${tags[*]}" >>"$GITHUB_OUTPUT"
