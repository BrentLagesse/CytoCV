#!/usr/bin/env bash

set -euo pipefail

readonly REQUIRED_PYTHON_VERSION="3.11.5"
readonly REPO_MARKER_REQUIREMENTS="requirements.txt"
readonly REPO_MARKER_MANAGE="cytocv/manage.py"
readonly ENV_RELATIVE=".env"
readonly WEIGHTS_RELATIVE="cytocv/core/weights/deepretina_final.h5"
readonly INSTALLER_HINT="bash scripts/local-install-windows.sh"
readonly -a VENV_CANDIDATES=(
    "cyto_cv/Scripts/python.exe"
    "cytocv_venv/Scripts/python.exe"
)

log() {
    printf '[INFO] %s\n' "$*" >&2
}

warn() {
    printf '[WARN] %s\n' "$*" >&2
}

fail() {
    printf '[ERROR] %s\n' "$*" >&2
    exit 1
}

require_git_bash() {
    local uname_out
    uname_out="$(uname -s)"
    case "${uname_out}" in
        MINGW*|MSYS*) ;;
        *)
            fail "This run script targets Git Bash on native Windows. Detected '${uname_out}'."
            ;;
    esac

    if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
        fail "This run script does not support WSL. Use Git Bash on a native Windows checkout."
    fi

    if ! command -v cygpath >/dev/null 2>&1; then
        fail "cygpath is required. Run this script from Git Bash."
    fi
}

find_repo_root() {
    local current_dir
    current_dir="$(pwd)"

    while [[ "${current_dir}" != "/" ]]; do
        if [[ -f "${current_dir}/${REPO_MARKER_REQUIREMENTS}" && -f "${current_dir}/${REPO_MARKER_MANAGE}" ]]; then
            printf '%s\n' "${current_dir}"
            return 0
        fi
        current_dir="$(dirname "${current_dir}")"
    done

    return 1
}

resolve_venv_python() {
    local repo_root="$1"
    local candidate

    for candidate in "${VENV_CANDIDATES[@]}"; do
        if [[ -x "${repo_root}/${candidate}" ]]; then
            printf '%s\n' "${repo_root}/${candidate}"
            return 0
        fi
    done

    return 1
}

validate_local_setup() {
    local repo_root="$1"
    local venv_python env_file manage_file python_version weights_file

    venv_python="$(resolve_venv_python "${repo_root}" || true)"
    env_file="${repo_root}/${ENV_RELATIVE}"
    manage_file="${repo_root}/${REPO_MARKER_MANAGE}"
    weights_file="${repo_root}/${WEIGHTS_RELATIVE}"

    [[ -f "${manage_file}" ]] || fail "Could not find ${REPO_MARKER_MANAGE} under the discovered repo root."
    [[ -n "${venv_python}" ]] || fail "Local virtual environment is missing. Expected one of: ${VENV_CANDIDATES[*]}. Run ${INSTALLER_HINT} from the repo root first."
    [[ -f "${env_file}" ]] || fail "Local .env is missing at ${env_file}. Run ${INSTALLER_HINT} from the repo root first."

    python_version="$("${venv_python}" -c "import sys; print(sys.version.split()[0])" 2>/dev/null || true)"
    if [[ "${python_version}" != "${REQUIRED_PYTHON_VERSION}" ]]; then
        fail "Local virtual environment is using Python ${python_version:-unknown}, expected ${REQUIRED_PYTHON_VERSION}. Run ${INSTALLER_HINT} from the repo root first."
    fi

    if [[ ! -f "${weights_file}" ]]; then
        warn "Weights file is missing at ${weights_file}. The server can start, but analysis will fail until you run ${INSTALLER_HINT}."
    fi
}

require_applied_migrations() {
    local repo_root="$1"
    local venv_python

    venv_python="$(resolve_venv_python "${repo_root}" || true)"
    [[ -n "${venv_python}" ]] || fail "Local virtual environment is missing. Expected one of: ${VENV_CANDIDATES[*]}."

    local migration_plan
    migration_plan="$(
        cd "${repo_root}/cytocv" &&
        "${venv_python}" manage.py migrate --plan 2>&1
    )" || fail "Could not inspect Django migrations. ${migration_plan}"

    if grep -Eq '^\s{2}Apply ' <<<"${migration_plan}"; then
        fail "Unapplied Django migrations detected. Run '${venv_python} ${repo_root}/cytocv/manage.py migrate' before starting the local server."
    fi
}

main() {
    local repo_root venv_python django_dir

    require_git_bash

    if ! repo_root="$(find_repo_root)"; then
        fail "Could not find the CytoCV repo root from the current directory. Launch this script from somewhere inside the CytoCV repo tree."
    fi

    venv_python="$(resolve_venv_python "${repo_root}" || true)"
    django_dir="${repo_root}/cytocv"

    validate_local_setup "${repo_root}"
    require_applied_migrations "${repo_root}"

    log "Discovered repo root: ${repo_root}"
    log "Using Python: ${venv_python}"
    log "Starting Django runserver from ${django_dir}"

    cd "${django_dir}"
    exec "${venv_python}" manage.py runserver "$@"
}

main "$@"
