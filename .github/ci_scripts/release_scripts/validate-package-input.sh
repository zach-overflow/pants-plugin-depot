#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${PACKAGE}" ]]; then
	echo "::notice::No package given; releasing every plugin with pending changes."
	exit 0
fi
if ! grep -Fxq "[monorepo.packages.${PACKAGE}]" cog.toml; then
	packages="$(sed -nE 's/^\[monorepo\.packages\.([^]]+)\]$/\1/p' cog.toml)"
	echo "::error::'${PACKAGE}' is not a package in cog.toml. Valid packages: ${packages//$'\n'/ }"
	exit 1
fi
echo "::notice::Releasing only '${PACKAGE}'."
