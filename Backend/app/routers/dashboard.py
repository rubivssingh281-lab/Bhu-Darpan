"""Dashboard aggregation route — computes live statistics from stored analyses."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..database import db
from ..deps import get_current_user
from ..services.constants import CLASSES

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _mean_land_cover(items: list[dict]) -> dict[str, float]:
    out = {c: 0.0 for c in CLASSES}
    if not items:
        return out
    for it in items:
        lc = it.get("land_cover", {})
        for c in CLASSES:
            out[c] += float(lc.get(c, 0.0))
    return {c: round(out[c] / len(items), 2) for c in CLASSES}


@router.get("")
def dashboard(user: dict = Depends(get_current_user)):
    analyses = db.analyses.find({"owner": user["id"]})
    analyses.sort(key=lambda d: d.get("created_at", ""))
    changes = db.changes.find({"owner": user["id"]})

    n = len(analyses)

    # Land-cover distribution (mean over all analyses) -> donut chart
    land_cover = _mean_land_cover(analyses)

    # Area change vs previous period: newer half vs older half
    if n >= 2:
        mid = n // 2
        older = analyses[:mid]
        newer = analyses[mid:]
        prev_lc = _mean_land_cover(older)
        curr_lc = _mean_land_cover(newer)
        land_cover_delta = {c: round(curr_lc[c] - prev_lc[c], 2) for c in CLASSES}
    else:
        land_cover_delta = {c: 0.0 for c in CLASSES}

    # Object totals across analyses
    object_totals: dict[str, int] = {}
    for it in analyses:
        for k, v in it.get("object_counts", {}).items():
            object_totals[k] = object_totals.get(k, 0) + int(v)

    avg_conf = round(sum(it.get("confidence", 0) for it in analyses) / n, 1) if n else 0.0
    reports = sum(1 for it in analyses if it.get("report_url"))

    recent = []
    for it in reversed(analyses[-6:]):
        lc = it.get("land_cover", {})
        dominant = max(lc, key=lc.get) if lc else "—"
        recent.append({
            "id": it["id"],
            "name": it["name"],
            "created_at": it["created_at"],
            "thumb": it.get("segmentation_url"),
            "confidence": it.get("confidence", 0),
            "dominant": dominant,
            "report_url": it.get("report_url"),
        })

    # Confidence trend (chronological)
    trend = [{"name": it["name"], "confidence": it.get("confidence", 0)} for it in analyses]

    return {
        "backend": db.info(),
        "totals": {
            "images": n,
            "changes": len(changes),
            "reports": reports,
            "objects": sum(object_totals.values()),
        },
        "avg_confidence": avg_conf,
        "land_cover": land_cover,
        "land_cover_delta": land_cover_delta,
        "object_totals": object_totals,
        "recent": recent,
        "trend": trend,
    }
