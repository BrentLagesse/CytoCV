#!/usr/bin/env bash

set -euo pipefail

readonly -a REQUIRED_LIBRARIES=(
  "libGL.so.1"
  "libglib-2.0.so.0"
)
readonly -a APT_PACKAGES=(
  "libgl1"
  "libglib2.0-0"
)

runtime_libraries="$(ldconfig -p 2>/dev/null || true)"
missing_libraries=()
for library in "${REQUIRED_LIBRARIES[@]}"; do
  if ! grep -Fq "$library" <<<"$runtime_libraries"; then
    missing_libraries+=("$library")
  fi
done

if (( ${#missing_libraries[@]} == 0 )); then
  echo "OpenCV runtime libraries are already available; skipping apt."
  exit 0
fi

echo "Installing missing OpenCV runtime libraries: ${missing_libraries[*]}"

# Hosted-runner Ubuntu mirrors can occasionally accept a connection and then
# stop responding. Keep apt's own retries short and enforce a hard ceiling so
# dependency setup cannot consume the job-level timeout.
readonly -a APT_OPTIONS=(
  -o "Acquire::Retries=3"
  -o "Acquire::http::Timeout=15"
  -o "Acquire::https::Timeout=15"
)

run_apt() {
  sudo timeout --signal=TERM --kill-after=30s 3m \
    apt-get "${APT_OPTIONS[@]}" "$@"
}

run_apt update
run_apt install -y --no-install-recommends "${APT_PACKAGES[@]}"

runtime_libraries="$(ldconfig -p 2>/dev/null || true)"
for library in "${REQUIRED_LIBRARIES[@]}"; do
  if ! grep -Fq "$library" <<<"$runtime_libraries"; then
    echo "Required OpenCV runtime library is still unavailable: $library" >&2
    exit 1
  fi
done
