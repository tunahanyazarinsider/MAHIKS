"""
Eval Controller for MAHIKS-TR
Read-only access to the evaluation reports produced by scripts/evaluate_api.py.
"""
import json
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from backend.core.security import get_current_user
from backend.core.api_response import success_response


eval_router = APIRouter(prefix="/api/eval", tags=["eval"])


# Eval reports are produced as `eval_api_report_YYYYMMDD_HHMMSS.json` by
# scripts/evaluate_api.py. The regex is intentionally strict — the filename
# is sent into a Path concatenation, so anything beyond letters / digits /
# the underscore separator and the .json suffix is rejected.
_FILENAME_RE = re.compile(r"^eval_api_report_[0-9_]+\.json$")

# Reports live in the repo's data/ directory. Use the working directory
# rather than __file__ — the container's WORKDIR is /app and that's where
# `data/` is mounted. Resolved here so we get a real absolute path and can
# protect against symlink escapes if needed later.
_DATA_DIR = Path("data").resolve()


def _safe_report_path(filename: str) -> Path:
    """Validate filename and resolve to an absolute path under data/.

    Rejects anything that doesn't match the strict regex, and verifies the
    resolved file is still under _DATA_DIR (defence-in-depth — the regex
    alone already excludes path separators)."""
    if not _FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    candidate = (_DATA_DIR / filename).resolve()
    try:
        candidate.relative_to(_DATA_DIR)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return candidate


@eval_router.get("/reports")
async def list_reports(_=Depends(get_current_user)):
    """List every eval report on disk, newest first."""
    if not _DATA_DIR.exists():
        return success_response(data=[])

    reports = []
    for path in sorted(_DATA_DIR.glob("eval_api_report_*.json"), reverse=True):
        if not _FILENAME_RE.match(path.name):
            continue
        try:
            # Read only the small top-level fields; results[] can be ~300KB.
            # json.loads of the whole file is still cheap enough at this size
            # but we slice down to what the list view actually needs.
            raw = json.loads(path.read_text(encoding="utf-8"))
            reports.append({
                "filename": path.name,
                "timestamp": raw.get("timestamp"),
                "api_url": raw.get("api_url"),
                "judge": raw.get("judge"),
                "questions_file": raw.get("questions_file"),
                "summary": raw.get("summary", {}),
            })
        except (json.JSONDecodeError, OSError) as e:
            # Don't fail the whole list on one bad file.
            reports.append({
                "filename": path.name,
                "error": f"Failed to parse: {e}",
            })

    return success_response(data=reports)


@eval_router.get("/reports/{filename}")
async def get_report(filename: str, _=Depends(get_current_user)):
    """Return one full eval report, including per-question results."""
    path = _safe_report_path(filename)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse report: {e}")
    return success_response(data=data)
