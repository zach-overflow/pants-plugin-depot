#!/usr/bin/env bash

set -euo pipefail

target="provides/${PACKAGE}:plugin-oci-artifact"
# Only plugins whose BUILD calls `plugin_wheel(include_oci_pex=True)` define the target (see
# `etc/pants-macros/_internal_pants_macros.py`); the rest publish a wheel only.
if ! pants list "provides/${PACKAGE}:" | grep -qx "${target}"; then
	echo "::notice::provides/${PACKAGE} defines no :plugin-oci-artifact target; skipping the OCI artifact publish."
	exit 0
fi
output=dist/publish-oci-artifact.json
# `pants publish` builds everything in its sandbox, so `dist/` does not exist on a fresh checkout, and
# Pants writes `--publish-output` without creating its parent directory.
mkdir -p "$(dirname "${output}")"
pants publish "${target}" --publish-output="${output}"
jq . "${output}"
# `[oras].allow_publish` is only true in pants.ci.toml; a skipped publish means it was not applied.
if ! jq -e '.[] | select(.publisher == "oras") | select(.status | startswith("published"))' "${output}" >/dev/null; then
	echo "::error::${target} was not published; see the publish output above."
	exit 1
fi
# The tag checkout must have versioned the artifact exactly `<version>`, as build-wheel checks for the wheel.
if ! jq -e --arg version "${VERSION}" \
	'.[] | select(.publisher == "oras") | select(.tags | index($version))' "${output}" >/dev/null; then
	echo "::error::The OCI artifact of provides/${PACKAGE} was not tagged ${VERSION}; vcs-versioning did not see the \
tag on HEAD (shallow or dirty checkout)."
	exit 1
fi
