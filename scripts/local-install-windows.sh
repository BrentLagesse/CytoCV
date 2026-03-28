#!/usr/bin/env bash

set -euo pipefail

readonly REQUIRED_PYTHON_VERSION="3.11.5"
readonly WEIGHTS_URL="https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing"
readonly MIN_WEIGHTS_SIZE_BYTES=100000000

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${REPO_ROOT}/.cytocv-local-install"
LOG_FILE="${STATE_DIR}/install.log"
SUMMARY_FILE="${STATE_DIR}/summary.txt"
REQUIREMENTS_HASH_FILE="${STATE_DIR}/requirements.sha256"
VENV_DIR="${REPO_ROOT}/cyto_cv"
VENV_PYTHON="${VENV_DIR}/Scripts/python.exe"
VENV_PIP="${VENV_DIR}/Scripts/pip.exe"
ENV_FILE="${REPO_ROOT}/.env"
ENV_EXAMPLE="${REPO_ROOT}/.env.example"
REQUIREMENTS_FILE="${REPO_ROOT}/requirements.txt"
DJANGO_DIR="${REPO_ROOT}/cytocv"
WEIGHTS_PATH="${DJANGO_DIR}/core/weights/deepretina_final.h5"

mkdir -p "${STATE_DIR}"
: > "${LOG_FILE}"
: > "${SUMMARY_FILE}"
exec > >(tee -a "${LOG_FILE}") 2>&1

summary() {
    printf '%s\n' "$*" | tee -a "${SUMMARY_FILE}" >/dev/null
}

log() {
    printf '[INFO] %s\n' "$*" >&2
}

warn() {
    printf '[WARN] %s\n' "$*" >&2
}

fail() {
    printf '[ERROR] %s\n' "$*" >&2
    summary "[ERROR] $*"
    exit 1
}

mark_run() {
    local message="$1"
    log "${message}"
    summary "[RUN] ${message}"
}

mark_skip() {
    local message="$1"
    log "${message}"
    summary "[SKIP] ${message}"
}

require_git_bash() {
    local uname_out
    uname_out="$(uname -s)"
    case "${uname_out}" in
        MINGW*|MSYS*) ;;
        *)
            fail "This installer targets Git Bash on native Windows. Detected '${uname_out}'."
            ;;
    esac

    if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
        fail "This installer does not support WSL. Use Git Bash on a native Windows checkout."
    fi

    if ! command -v cygpath >/dev/null 2>&1; then
        fail "cygpath is required. Run this installer from Git Bash."
    fi
}

windows_path_to_unix() {
    cygpath -u "$1"
}

find_python_3115() {
    local result version executable unix_executable
    if command -v py.exe >/dev/null 2>&1; then
        result="$(py.exe -3.11 -c "import sys; print(sys.version.split()[0]); print(sys.executable)" 2>/dev/null || true)"
        if [[ -n "${result}" ]]; then
            version="$(printf '%s\n' "${result}" | sed -n '1p')"
            executable="$(printf '%s\n' "${result}" | sed -n '2p')"
            if [[ "${version}" == "${REQUIRED_PYTHON_VERSION}" && -n "${executable}" ]]; then
                unix_executable="$(windows_path_to_unix "${executable}")"
                if [[ -x "${unix_executable}" ]]; then
                    printf '%s\n' "${unix_executable}"
                    return 0
                fi
            fi
        fi
    fi

    if command -v python.exe >/dev/null 2>&1; then
        result="$(python.exe -c "import sys; print(sys.version.split()[0]); print(sys.executable)" 2>/dev/null || true)"
        if [[ -n "${result}" ]]; then
            version="$(printf '%s\n' "${result}" | sed -n '1p')"
            executable="$(printf '%s\n' "${result}" | sed -n '2p')"
            if [[ "${version}" == "${REQUIRED_PYTHON_VERSION}" && -n "${executable}" ]]; then
                unix_executable="$(windows_path_to_unix "${executable}")"
                if [[ -x "${unix_executable}" ]]; then
                    printf '%s\n' "${unix_executable}"
                    return 0
                fi
            fi
        fi
    fi

    return 1
}

install_python_3115_with_winget() {
    if ! command -v winget.exe >/dev/null 2>&1; then
        fail "winget.exe was not found. Install Python ${REQUIRED_PYTHON_VERSION} manually, then rerun this script."
    fi

    mark_run "Installing Python ${REQUIRED_PYTHON_VERSION} with winget"
    winget.exe install \
        --id Python.Python.3.11 \
        --version "${REQUIRED_PYTHON_VERSION}" \
        --exact \
        --accept-package-agreements \
        --accept-source-agreements \
        --disable-interactivity \
        || fail "winget could not install Python ${REQUIRED_PYTHON_VERSION}. Install it manually and rerun."
}

ensure_python_3115() {
    local python_path
    if python_path="$(find_python_3115)"; then
        mark_skip "Using existing Python ${REQUIRED_PYTHON_VERSION} at ${python_path}"
        printf '%s\n' "${python_path}"
        return 0
    fi

    install_python_3115_with_winget

    if python_path="$(find_python_3115)"; then
        printf '%s\n' "${python_path}"
        return 0
    fi

    fail "Python ${REQUIRED_PYTHON_VERSION} is still not available after winget install. Verify the exact version manually, then rerun."
}

ensure_venv() {
    local base_python="$1"
    local venv_version

    if [[ -x "${VENV_PYTHON}" ]]; then
        venv_version="$("${VENV_PYTHON}" -c "import sys; print(sys.version.split()[0])" 2>/dev/null || true)"
        if [[ "${venv_version}" == "${REQUIRED_PYTHON_VERSION}" ]]; then
            mark_skip "Virtual environment already exists at ${VENV_DIR}"
            return 0
        fi
        fail "Existing virtual environment at ${VENV_DIR} is using Python ${venv_version:-unknown}, not ${REQUIRED_PYTHON_VERSION}. Remove cyto_cv and rerun."
    fi

    mark_run "Creating virtual environment at ${VENV_DIR}"
    "${base_python}" -m venv "${VENV_DIR}"
}

requirements_hash() {
    sha256sum "${REQUIREMENTS_FILE}" | awk '{print $1}'
}

ensure_dependencies() {
    local current_hash stored_hash
    current_hash="$(requirements_hash)"

    if [[ -x "${VENV_PIP}" && -f "${REQUIREMENTS_HASH_FILE}" ]]; then
        stored_hash="$(<"${REQUIREMENTS_HASH_FILE}")"
        if [[ "${stored_hash}" == "${current_hash}" ]] && "${VENV_PIP}" check >/dev/null 2>&1; then
            mark_skip "Python dependencies already satisfy requirements.txt"
            return 0
        fi
    fi

    mark_run "Installing Python dependencies into ${VENV_DIR}"
    "${VENV_PYTHON}" -m pip install --upgrade pip setuptools wheel
    "${VENV_PIP}" install -r "${REQUIREMENTS_FILE}" --no-cache-dir
    "${VENV_PIP}" check >/dev/null
    printf '%s\n' "${current_hash}" > "${REQUIREMENTS_HASH_FILE}"
}

get_env_value() {
    local key="$1"
    if [[ ! -f "${ENV_FILE}" ]]; then
        return 0
    fi
    awk -F= -v target="${key}" '
        $1 == target {
            sub(/^[[:space:]]+/, "", $2)
            sub(/[[:space:]]+$/, "", $2)
            print $2
            exit
        }
    ' "${ENV_FILE}"
}

append_env_if_missing() {
    local key="$1"
    local value="$2"
    if grep -Eq "^${key}=" "${ENV_FILE}"; then
        return 0
    fi
    printf '%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
}

ensure_env_file() {
    local current_db current_debug

    if [[ ! -f "${ENV_FILE}" ]]; then
        mark_run "Creating .env from .env.example"
        cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    else
        mark_skip "Using existing .env at ${ENV_FILE}"
    fi

    current_db="$(get_env_value "CYTOCV_DB_BACKEND")"
    current_debug="$(get_env_value "CYTOCV_DEBUG")"

    if [[ -n "${current_db}" && "${current_db}" != "sqlite" ]]; then
        fail "Existing .env sets CYTOCV_DB_BACKEND=${current_db}. This installer only supports local SQLite. Update .env manually or use a separate environment."
    fi
    if [[ -n "${current_debug}" && "${current_debug}" != "1" ]]; then
        fail "Existing .env sets CYTOCV_DEBUG=${current_debug}. This installer requires CYTOCV_DEBUG=1 for local SQLite."
    fi

    mark_run "Patching missing local-safe defaults in .env"
    append_env_if_missing "CYTOCV_SECRET_KEY" "change-me-local"
    append_env_if_missing "CYTOCV_DEBUG" "1"
    append_env_if_missing "CYTOCV_ALLOWED_HOSTS" "localhost,127.0.0.1"
    append_env_if_missing "CYTOCV_DB_BACKEND" "sqlite"
    append_env_if_missing "CYTOCV_ACCOUNT_EMAIL_VERIFICATION" "none"
    append_env_if_missing "CYTOCV_RECAPTCHA_ENABLED" "0"
}

ensure_gdown() {
    if "${VENV_PYTHON}" -c "import gdown" >/dev/null 2>&1; then
        mark_skip "gdown is already available in the virtual environment"
        return 0
    fi

    mark_run "Installing gdown into the virtual environment"
    "${VENV_PIP}" install gdown
}

weights_are_valid() {
    [[ -f "${WEIGHTS_PATH}" ]] || return 1
    local size
    size="$(wc -c < "${WEIGHTS_PATH}")"
    [[ "${size}" -ge "${MIN_WEIGHTS_SIZE_BYTES}" ]]
}

ensure_weights() {
    mkdir -p "$(dirname "${WEIGHTS_PATH}")"

    if weights_are_valid; then
        mark_skip "Mask R-CNN weights already present at ${WEIGHTS_PATH}"
        return 0
    fi

    ensure_gdown
    mark_run "Downloading Mask R-CNN weights to ${WEIGHTS_PATH}"
    "${VENV_PYTHON}" -m gdown --fuzzy "${WEIGHTS_URL}" -O "${WEIGHTS_PATH}" \
        || fail "Failed to download deepretina_final.h5. Resolve the network or Google Drive access issue and rerun."

    if ! weights_are_valid; then
        fail "Weights file at ${WEIGHTS_PATH} is missing or incomplete after download."
    fi
}

print_migration_recovery_guidance() {
    cat <<'EOF'

Known local migration recovery path:

    cd ..
    rm -f cytocv/accounts/migrations/0001_initial.py
    rm -f cytocv/core/migrations/0001_initial.py
    rm -f cytocv/core/migrations/0007_uploadedimage_scale_info.py
    cd cytocv
    python manage.py makemigrations accounts core
    python manage.py migrate
    python manage.py check

This installer intentionally stops here instead of rewriting tracked migration files automatically.
Resolve the migration issue, then rerun scripts/local-install-windows.sh.
EOF
}

run_migrations_and_checks() {
    mark_run "Running Django migrations"
    if ! (
        cd "${DJANGO_DIR}" &&
        "${VENV_PYTHON}" manage.py migrate
    ); then
        print_migration_recovery_guidance
        fail "Django migrations failed."
    fi

    mark_run "Running Django system checks"
    (
        cd "${DJANGO_DIR}" &&
        "${VENV_PYTHON}" manage.py check
    ) || fail "python manage.py check failed."
}

validate_runtime_imports() {
    mark_run "Validating cv2 and tensorflow imports"
    "${VENV_PYTHON}" -c "import cv2, tensorflow as tf; print('cv2', cv2.__version__); print('tensorflow', tf.__version__)" \
        || fail "Runtime import validation failed."
}

print_success_summary() {
    summary "[OK] Local installation completed successfully"
    cat <<EOF

Local installation completed successfully.

State files:
  Log: ${LOG_FILE}
  Summary: ${SUMMARY_FILE}

Next steps:
  1. Open Git Bash in the repo root.
  2. Start the development server:

     cd "${REPO_ROOT}/cytocv"
     ../cyto_cv/Scripts/python.exe manage.py runserver

  3. Open http://localhost:8000/

Rerun behavior:
  - Re-running this script is safe.
  - Completed steps are skipped only when their current outputs are still valid.
EOF
}

main() {
    local python_3115

    require_git_bash
    summary "CytoCV smart Windows local installer"
    summary "Repository root: ${REPO_ROOT}"

    python_3115="$(ensure_python_3115)"
    ensure_venv "${python_3115}"
    ensure_dependencies
    ensure_env_file
    ensure_weights
    run_migrations_and_checks
    validate_runtime_imports
    print_success_summary
}

main "$@"
