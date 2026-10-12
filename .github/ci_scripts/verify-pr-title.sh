#!/usr/bin/env bash

set -euo pipefail

git config --global user.name github-actions
git config --global user.email "github-actions[bot]@users.noreply.github.com"
if ! cog verify "${PR_TITLE}"; then
	echo "::error::PR title '${PR_TITLE}' is not a conventional commit message. It becomes the \
squash commit on the default branch, so it must parse (e.g. 'feat(scope): ...', 'fix: ...', \
'feat!: ...' for breaking changes)."
	exit 1
fi
