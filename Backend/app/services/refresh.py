"""Near-real-time data refresh.

Pulls the latest available window from the live national/open reanalysis feeds
(NASA POWER — MERRA-2), re-runs the ingest ETL (download → regrid → NetCDF +
manifest), and clears the per-cell analysis caches so the Climate Map immediately
reflects the new data. Exposes status (last-refresh time, latency) for the UI and
an optional background scheduler for continuous (near-real-time) operation.

Reanalysis feeds have an inherent few-day latency, so the "current" window ends a
few days before today — this is stated honestly in the status payload.
"""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta, timezone

from ..config import settings

log = logging.getLogger("bhu-darpan.refresh")

_LATENCY_DAYS = 3          # NASA POWER availability lag
_WINDOW_DAYS = 30
# Every live layer the twin shows, as (source, var, region). Both J&K reanalyses share
# the SAME window so multi-source fusion always has a contemporaneous pair; LST feeds
# surface fusion; the India layers back the national view of the Climate Map.
_JOBS = (("power", "rain", "jk"), ("power", "tmean", "jk"), ("power", "lst", "jk"),
         ("openmeteo", "rain", "jk"), ("openmeteo", "tmean", "jk"),
         ("power", "rain", "india"), ("power", "tmean", "india"))
_lock = threading.Lock()
_state: dict = {"last_refresh": None, "last_result": None, "running": False}


def _target_window() -> tuple[str, str]:
    end = date.today() - timedelta(days=_LATENCY_DAYS)
    start = end - timedelta(days=_WINDOW_DAYS)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def is_stale() -> bool:
    """True when any live layer's newest ingested window ends before the target end."""
    try:
        from ingest.pipeline import _load_manifest
        _, target_end = _target_window()
        ends = {}
        for d in _load_manifest().get("datasets", []):
            if d.get("kind") == "climatology" or not d.get("end"):
                continue
            key = (d.get("id", "").split("_")[0], d.get("var"), d.get("region"))
            ends[key] = max(ends.get(key, ""), d["end"])
        return any(ends.get(job, "") < target_end for job in _JOBS)
    except Exception:
        return True


def latest_end(source: str) -> str | None:
    """Newest ingested day (YYYYMMDD) for a live source ('power' / 'openmeteo'), or None."""
    try:
        from ingest.pipeline import _load_manifest
        ends = [d["end"] for d in _load_manifest().get("datasets", [])
                if d.get("kind") != "climatology" and d.get("end")
                and d.get("id", "").split("_")[0] == source]
        return max(ends) if ends else None
    except Exception:
        return None


def status() -> dict:
    return dict(_state)


def _clear_caches() -> None:
    from . import gridded_analysis
    for name in ("anomaly", "forecast_field", "forecast_skill", "districts"):
        fn = getattr(gridded_analysis, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            try:
                fn.cache_clear()
            except Exception:
                pass
    try:
        from . import fusion
        if hasattr(fusion, "fuse") and hasattr(fusion.fuse, "cache_clear"):
            fusion.fuse.cache_clear()
    except Exception:
        pass
    try:   # per-cell forecast re-seeds from the newest daily grid
        from . import grid_ml_forecast
        grid_ml_forecast.forecast_field.cache_clear()
    except Exception:
        pass
    try:   # 14-day outlooks + derived soil/drought use the refreshed state
        from . import climate
        climate._FC_CACHE.clear()
    except Exception:
        pass


def refresh_now(region: str | None = None, jobs: tuple = _JOBS) -> dict:
    """Fetch the latest window for every live layer (optionally only `region`) and update
    the manifest. Thread-safe."""
    with _lock:
        if _state["running"]:
            return {"status": "busy", "message": "a refresh is already in progress"}
        _state["running"] = True
    try:
        from ingest import pipeline
        s, e = _target_window()
        if region:
            jobs = tuple(j for j in jobs if j[2] == region)

        updated, errors = [], []
        for source, var, reg in jobs:
            try:
                entry = pipeline.run(source, var, reg, s, e)
                updated.append({"source": source, "var": var, "region": reg, "days": entry["days"],
                                "period": f"{entry['start']}–{entry['end']}",
                                "mean": entry["mean"], "units": entry["units"]})
            except Exception as exc:
                log.warning("refresh %s/%s/%s failed: %s", source, var, reg, exc)
                errors.append({"source": source, "var": var, "region": reg, "error": str(exc)})

        if updated:
            _clear_caches()
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result = {
            "status": "ok" if updated and not errors else ("partial" if updated else "failed"),
            "region": region or "all", "window": f"{s}–{e}",
            "latency_days": _LATENCY_DAYS, "updated": updated, "errors": errors,
            "at": ts,
        }
        _state["last_refresh"] = ts
        _state["last_result"] = result
        return result
    finally:
        _state["running"] = False


def warm() -> None:
    """Pre-compute the heavy cached analyses (live record tail, 14-day outlooks, per-cell
    forecaster, fusion) so the first page load after a start/refresh is instant."""
    from . import climate, fusion, grid_ml_forecast, hazards
    steps = (lambda: hazards._data(),
             lambda: climate.forecast("temperature"), lambda: climate.forecast("rainfall"),
             lambda: grid_ml_forecast.train("tmean", "jk"), lambda: grid_ml_forecast.train("rain", "jk"),
             lambda: fusion.fuse("rain", "jk"), lambda: fusion.fuse("tmean", "jk"))
    for step in steps:
        try:
            step()
        except Exception as exc:
            log.warning("warm-up step failed: %s", exc)


def start_scheduler() -> None:
    """Background loop: refresh at startup when the data is stale, warm the caches, then
    refresh every settings.auto_refresh_hours hours (default 6; 0 disables refreshing but
    still warms). Never blocks startup."""
    hours = getattr(settings, "auto_refresh_hours", 6)
    if not hours or hours <= 0:
        threading.Thread(target=warm, daemon=True, name="cache-warmup").start()
        return

    def _loop():
        import time
        interval = hours * 3600
        first = True
        while True:
            try:
                if not first or is_stale():
                    refresh_now()
            except Exception as exc:
                log.warning("scheduled refresh error: %s", exc)
            warm()
            first = False
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True, name="refresh-scheduler").start()
    log.info("near-real-time refresh scheduler started (every %sh)", hours)
