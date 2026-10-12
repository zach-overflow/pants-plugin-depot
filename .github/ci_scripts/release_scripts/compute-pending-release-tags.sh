#!/usr/bin/env bash

set -euo pipefail

args=(bump --auto --dry-run)
if [[ -n "${PACKAGE}" ]]; then
	args+=(--package "${PACKAGE}")
fi
pending="$(cog "${args[@]}")"
if ! grep -Eq '^[a-z0-9][a-z0-9-]*-v[0-9]+\.[0-9]+\.[0-9]+$' <<<"${pending}"; then
	echo "::error::No plugin has a commit that warrants a release (cog printed '${pending}')."
	exit 1
fi
if [[ -n "${PACKAGE}" && ! "${pending}" =~ ^${PACKAGE}-v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
	echo "::error::'${PACKAGE}' has no commit that warrants a release (cog printed '${pending}')."
	exit 1
fi
echo "::notice::Validating ${GITHUB_SHA} for release: ${pending//$'\n'/ }"
