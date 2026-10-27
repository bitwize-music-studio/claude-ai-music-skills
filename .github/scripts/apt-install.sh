#!/usr/bin/env bash
# Install apt packages on a GitHub-hosted Ubuntu runner without depending on
# the runner's own mirror being fast.
#
#   bash .github/scripts/apt-install.sh [apt-get install options] PACKAGE...
#
# The runner image points apt at azure.archive.ubuntu.com. From 2026-10-22 that
# mirror repeatedly sent packages at 30-40 KB/s. ffmpeg's 87 packages (62.8 MB)
# normally take 15-35 s, but four nightly legs ran into the 10-minute step
# timeout: 10-23, 10-26 twice (#595) and 10-27. Data kept arriving, so
# Acquire::http::Timeout never fired, and a longer step timeout would not help:
# at that rate the download takes about half an hour.
#
# So the fetch (index update plus --download-only) gets APT_FETCH_TIMEOUT
# seconds, 240 by default, on the runner's mirror. If it fails or runs out of
# time, the apt sources switch to archive.ubuntu.com and the fetch resumes
# there; .debs already in /var/cache/apt/archives are kept. The install then
# runs from that cache, so the time limit can only ever cut a download short,
# never dpkg.
#
# $APT_OPTS (workflow env) applies to every apt-get call. No -qq anywhere: the
# Get:/Hit: lines are the only record of which mirror a slow step was waiting on.
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "usage: $0 [apt-get install options] PACKAGE..." >&2
  exit 2
fi

fetch_timeout="${APT_FETCH_TIMEOUT:-240}"
case "$fetch_timeout" in
  '' | *[!0-9]* | 0)
    echo "APT_FETCH_TIMEOUT must be a positive whole number of seconds, got '$fetch_timeout'" >&2
    exit 2
    ;;
esac
read -r -a apt_opts <<< "${APT_OPTS:-}"

# apt-get as root. With a time limit, timeout runs as root as well, so its TERM
# (and the KILL 30 s later) reach apt-get itself rather than stopping at sudo.
apt_get() {
  local limit=$1
  shift
  if [ "$limit" -gt 0 ]; then
    sudo timeout --kill-after=30 "$limit" apt-get "${apt_opts[@]}" "$@"
  else
    sudo apt-get "${apt_opts[@]}" "$@"
  fi
}

# One deadline for the whole first fetch: the 2026-08-19 nightly hung inside
# `apt-get update` itself, so the index update counts against the limit too.
deadline=$((SECONDS + fetch_timeout))
time_left() {
  local left=$((deadline - SECONDS))
  echo $((left > 0 ? left : 1))
}

status=0
{
  apt_get "$(time_left)" update &&
    apt_get "$(time_left)" install -y --download-only "$@"
} || status=$?

if [ "$status" -ne 0 ]; then
  case "$status" in
    124 | 137) reason="ran past ${fetch_timeout}s" ;;
    *) reason="failed (exit $status)" ;;
  esac
  echo "::warning title=apt mirror fallback::fetching from the runner's mirror $reason; retrying from archive.ubuntu.com"
  mapfile -t sources < <(grep -rlF azure.archive.ubuntu.com /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null || true)
  if [ "${#sources[@]}" -gt 0 ]; then
    sudo sed -i 's#azure\.archive\.ubuntu\.com#archive.ubuntu.com#g' "${sources[@]}"
    echo "Now using archive.ubuntu.com in: ${sources[*]}"
  else
    echo "No apt source names azure.archive.ubuntu.com; retrying the configured mirrors."
  fi
  apt_get 0 update
  apt_get 0 install -y --download-only "$@"
fi

apt_get 0 install -y "$@"
