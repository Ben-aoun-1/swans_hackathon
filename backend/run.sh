#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
uvicorn app.main:app --reload --port 8000
