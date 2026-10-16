#!/usr/bin/env bash

set -euo pipefail

output=dist/publish-oci-artifact.json
pants publish "provides/${PACKAGE}:plugin-oci-artifact" --publish-output="${output}"
jq . "${output}"
# `[oras].allow_publish` is only true in pants.ci.toml; a skipped publish means it was not applied.
if ! jq -e '.[] | select(.publisher == "oras") | select(.status | startswith("published"))' "${output}" >/dev/null; then
	echo "::error::provides/${PACKAGE}:plugin-oci-artifact was not published; see the publish output above."
	exit 1
fi
# The tag checkout must have versioned the artifact exactly `<version>`, as build-wheel checks for the wheel.
if ! jq -e --arg version "${VERSION}" \
	'.[] | select(.publisher == "oras") | select(.tags | index($version))' "${output}" >/dev/null; then
	echo "::error::The OCI artifact of provides/${PACKAGE} was not tagged ${VERSION}; vcs-versioning did not see the \
tag on HEAD (shallow or dirty checkout)."
	exit 1
fi
