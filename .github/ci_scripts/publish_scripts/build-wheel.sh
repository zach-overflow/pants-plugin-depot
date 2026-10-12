#!/usr/bin/env bash

set -euo pipefail

pants package "provides/${PACKAGE}:plugin-whl"
wheels=(dist/*-"${VERSION}"-py3-none-any.whl)
if [[ "${#wheels[@]}" -ne 1 || ! -f "${wheels[0]}" ]]; then
	echo "::error::Expected exactly one wheel with version ${VERSION} from provides/${PACKAGE}:plugin-whl."
	ls -l dist
	exit 1
fi
ls -l "${wheels[0]}"
