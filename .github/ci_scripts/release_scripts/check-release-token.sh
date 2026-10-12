#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${GH_TOKEN}" ]]; then
	echo "::error::The 'release' environment has no RELEASE_TOKEN secret."
	exit 1
fi
if ! login="$(gh api user --jq .login)"; then
	echo "::error::GitHub rejected RELEASE_TOKEN. Re-create the token and update the secret."
	exit 1
fi
if ! admin="$(gh api "repos/${GITHUB_REPOSITORY}" --jq .permissions.admin)"; then
	echo "::error::RELEASE_TOKEN (user '${login}') cannot access ${GITHUB_REPOSITORY}. Grant the token this \
repository."
	exit 1
fi
if [[ "${admin}" != "true" ]]; then
	echo "::error::RELEASE_TOKEN belongs to '${login}', who is not an admin of ${GITHUB_REPOSITORY}. Only an \
admin's push bypasses the default branch's protection."
	exit 1
fi
echo "::notice::RELEASE_TOKEN authenticates as '${login}' (admin)."
