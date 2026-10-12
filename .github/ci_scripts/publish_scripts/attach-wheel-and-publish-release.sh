#!/usr/bin/env bash

set -euo pipefail

wheels=(dist/*.whl)
if [[ "${#wheels[@]}" -ne 1 || ! -f "${wheels[0]}" ]]; then
	echo "::error::Expected exactly one wheel in the artifact."
	exit 1
fi
wheel_name="$(basename "${wheels[0]}")"
if ! release="$(gh release view "${TAG}" --repo "${GITHUB_REPOSITORY}" --json isDraft,assets)"; then
	echo "::error::No GitHub release exists for tag ${TAG}. Release tags must be created via the \
Release workflow, whose approve-and-tag job drafts the release before dispatching Publish."
	exit 1
fi
if [[ "$(jq -r '.isDraft' <<<"${release}")" == "false" ]]; then
	if ! jq -e --arg name "${wheel_name}" '.assets | any(.name == $name)' <<<"${release}" >/dev/null; then
		echo "::error::Release ${TAG} is already published and immutable but lacks ${wheel_name}. \
Assets cannot be added after publication; cut a new release."
		exit 1
	fi
	echo "::notice::Release ${TAG} is already published with ${wheel_name}; nothing to do."
	exit 0
fi
gh release upload "${TAG}" "dist/${wheel_name}" --repo "${GITHUB_REPOSITORY}" --clobber
gh release edit "${TAG}" --repo "${GITHUB_REPOSITORY}" --draft=false
echo "::notice::Published release ${TAG} with ${wheel_name} attached."
