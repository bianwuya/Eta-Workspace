#!/bin/bash
set -euo pipefail
repo_url=${1:?credential-free repository URL}
branch=${2:?branch}
cached=${3:-0}
[[ "$branch" =~ ^[A-Za-z0-9._/-]+$ ]] || { echo 'Invalid branch' >&2; exit 2; }
[[ "$branch" != *..* && "$branch" != *'@{'* ]] || { echo 'Invalid branch' >&2; exit 2; }
command -v flock >/dev/null || { echo 'flock is required' >&2; exit 2; }
mkdir -p /opt/eta/sources /opt/eta/locks
repo_key=$(printf '%s' "${repo_url,,}" | sha256sum | cut -c1-12)
mirror=/opt/eta/sources/$repo_key.git
lock=/opt/eta/locks/eta-cloud-source-$repo_key.lock
exec 8>"$lock"
if ! flock -w 300 8; then
    echo 'Another source fetch is active for this repository' >&2
    exit 75
fi
if [[ ! -e "$mirror" ]]; then
    git init --bare --quiet "$mirror"
fi
[[ -f "$mirror/HEAD" ]] || { echo 'Invalid bare source mirror' >&2; exit 3; }
if [[ "$cached" != 1 ]]; then
    # GitHub HTTP/2 streams have intermittently ended with early EOF in WSL.
    # Keep the transport credential-free and force the more stable HTTP/1.1 path.
    git -c http.version=HTTP/1.1 -C "$mirror" fetch --no-tags "$repo_url" "+refs/heads/${branch}:refs/heads/${branch}"
fi
commit=$(git -C "$mirror" rev-parse "refs/heads/${branch}^{commit}")
tree=$(git -C "$mirror" rev-parse "refs/heads/${branch}^{tree}")
printf '{"commit":"%s","tree":"%s","sourceGit":"%s","transport":"linux-native"}\n' "$commit" "$tree" "$mirror"
