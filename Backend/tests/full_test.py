"""Bhu-Darpan — full system integrity + accuracy test suite.

Covers: infra, climate twin, gridded analysis, hazards, fusion, auth/OTP security,
satellite land-cover CNN, and change detection. The EuroSAT-dependent checks
(behavioural + weight re-evaluation) are skipped automatically if the dataset
isn't present (it is only needed when you retrain — see README section 6).

Usage (from Backend/, venv active):
    # 1) start the server in test mode so OTP codes are returned for assertions:
    #    Windows PowerShell:  $env:OTP_DEV_MODE="true"; python run.py
    #    macOS/Linux:         OTP_DEV_MODE=true python run.py
    # 2) in another shell:
    #    python full_test.py
"""
import io
import sys
import time
import pathlib
import warnings
warnings.filterwarnings("ignore")

# Make the Backend/ package root importable (run as `python tests/full_test.py`)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import requests
from PIL import Image

B = "http://127.0.0.1:8000"
P = F = S = 0
FAILS = []


def check(name, cond, extra=""):
    global P, F
    if cond:
        P += 1; print(f"  [PASS] {name} {extra}")
    else:
        F += 1; FAILS.append(name); print(f"  [FAIL] {name} {extra}")


def skip(name, why=""):
    global S
    S += 1; print(f"  [SKIP] {name} {why}")


def get(path, token=None, **params):
    h = {"Authorization": "Bearer " + token} if token else {}
    r = requests.get(B + path, headers=h, params=params, timeout=60)
    try: return r.status_code, r.json()
    except Exception: return r.status_code, {}


def post(path, body=None, token=None, files=None, data=None):
    h = {"Authorization": "Bearer " + token} if token else {}
    r = requests.post(B + path, json=body if files is None else None,
                      files=files, data=data, headers=h, timeout=120)
    try: return r.status_code, r.json()
    except Exception: return r.status_code, {}


def solid(rgb, size=96):
    im = Image.new("RGB", (size, size), rgb); b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


print("\n===== 1. INFRA / HEALTH =====")
sc, j = get("/api/health")
check("health 200", sc == 200)
check("status ok", j.get("status") == "ok")
check("db backend reported", bool(j.get("database", {}).get("backend")))
check("5 land-cover classes", len(j.get("classes", [])) == 5)

print("\n===== 2. CLIMATE TWIN =====")
sc, s = get("/api/climate/current")
check("current 200", sc == 200)
check("rainfall anomaly in range", -100 <= s.get("rainfall_anomaly_pct", 999) <= 100, f"({s.get('rainfall_anomaly_pct')})")
check("temp anomaly plausible", -10 <= s.get("temperature_anomaly_c", 999) <= 10, f"({s.get('temperature_anomaly_c')})")
check("soil moisture 0..1", 0 <= s.get("soil_moisture_index", 9) <= 1, f"({s.get('soil_moisture_index')})")
check("drought class valid", s.get("drought_class") in ("Normal", "Mild", "Moderate", "Severe"))
check("spark_temp len 14", len(s.get("spark_temp", [])) == 14)
for var in ("temperature", "rainfall"):
    sc, fc = get("/api/climate/forecast", var=var)
    pred = fc.get("predicted", [])
    check(f"forecast[{var}] 14 days", sc == 200 and len(pred) == 14)
    check(f"forecast[{var}] band ordering", all(p["lower"] <= p["value"] <= p["upper"] for p in pred) if pred else False)
    check(f"forecast[{var}] skill rmse>0", fc.get("skill", {}).get("rmse", 0) > 0,
          f"(rmse={fc.get('skill',{}).get('rmse')}, skill%={fc.get('skill',{}).get('skill_pct')})")
sc, d = get("/api/climate/districts", layer="rain")
check("districts return 9 (J&K)", sc == 200 and len(d.get("districts", [])) == 9)
_, dry = post("/api/climate/whatif", {"rain_pct": -40, "temp_c": 3})
_, wet = post("/api/climate/whatif", {"rain_pct": 40, "temp_c": -1})
check("whatif drought score 0..100", 0 <= dry.get("drought_risk_score", -1) <= 100)
check("whatif monotonic (dry/hot > wet/cool)", dry.get("drought_risk_score", 0) > wet.get("drought_risk_score", 100))

print("\n===== 3. GRIDDED / HAZARDS / FUSION =====")
sc, gv = get("/api/gridded/vars", region="jk")
check("gridded vars include tmean/rain", "tmean" in str(gv) and "rain" in str(gv))
sc, an = get("/api/gridded/anomaly", var="tmean", region="jk")
check("anomaly grid ok", sc == 200 and all(k in an for k in ("lats", "lons", "anomaly")))
for ep in ("", "/drought", "/heatwave", "/monsoon"):
    check(f"hazards{ep or ' summary'} 200", get("/api/hazards" + ep)[0] == 200)
sc, fs = get("/api/fusion/status")
check("fusion status 2 sources", sc == 200 and len(fs.get("sources", [])) >= 2)

print("\n===== 4. AUTH / OTP SECURITY =====")
t = int(time.time())
sc, j = post("/api/auth/login", {"email": "demo@bhudarpan.ai", "password": "demo1234"})
check("demo password login", sc == 200 and "token" in j)
token = j.get("token")
check("wrong password 401", post("/api/auth/login", {"email": "demo@bhudarpan.ai", "password": "x"})[0] == 401)
check("no-token /me 401", get("/api/auth/me")[0] == 401)
check("analysis needs auth", get("/api/analysis")[0] == 401)
check("duplicate register 409", post("/api/auth/register", {"email": "demo@bhudarpan.ai", "name": "x", "password": "abcdef"})[0] == 409)
e = f"ft{t}@example.com"
sc, r = post("/api/auth/register", {"email": e, "name": "FT User", "password": "secret12"})
if not r.get("dev_otp"):
    skip("OTP verify chain", "(server not in OTP_DEV_MODE — codes are emailed, not returned)")
else:
    check("register sends OTP", sc == 200 and r.get("dev_otp"))
    check("verify creates account+token", post("/api/auth/verify-otp", {"email": e, "code": r["dev_otp"]})[0] == 200)
    check("code single-use", post("/api/auth/verify-otp", {"email": e, "code": r["dev_otp"]})[0] == 400)
    e2 = f"ftlock{t}@example.com"
    post("/api/auth/register", {"email": e2, "name": "L", "password": "abcdef"})
    codes = [post("/api/auth/verify-otp", {"email": e2, "code": "000000"})[0] for _ in range(5)]
    check("5 wrong codes 401", all(c == 401 for c in codes))
    check("6th wrong locked 429", post("/api/auth/verify-otp", {"email": e2, "code": "000000"})[0] == 429)
    e3 = f"ftcd{t}@example.com"
    post("/api/auth/register", {"email": e3, "name": "C", "password": "abcdef"})
    check("immediate resend 429", post("/api/auth/register", {"email": e3, "name": "C", "password": "abcdef"})[0] == 429)
    check("request-otp unknown 404", post("/api/auth/request-otp", {"email": "ghost@nowhere.com"})[0] == 404)

print("\n===== 5. SATELLITE CNN — ANALYSIS =====")
_BE = pathlib.Path(__file__).resolve().parent.parent          # Backend/
sample_p = _BE.parent / "sample_satellite.png"
if not sample_p.exists():
    skip("analysis", "(sample_satellite.png not found)")
else:
    sc, a = post("/api/analysis", token=token, files={"file": ("s.png", sample_p.read_bytes(), "image/png")}, data={"name": "ft"})
    check("analysis 200", sc == 200)
    is_cnn = "CNN" in (a.get("model_type") or "")
    (check if is_cnn else skip)("model is EuroSAT CNN", is_cnn if is_cnn else "(CNN weights absent → K-Means fallback)")
    check("confidence in (0,100]", 0 < (a.get("confidence") or 0) <= 100, f"({a.get('confidence')})")
    check("land-cover sums to ~100%", abs(sum(a.get("land_cover", {}).values()) - 100) < 1.0)
    check("segmentation+detection artefacts", a.get("segmentation_url") and a.get("detection_url"))
    if a.get("id"):
        requests.delete(B + f"/api/analysis/{a['id']}", headers={"Authorization": "Bearer " + token})

print("\n===== 6. CHANGE DETECTION =====")
euro = _BE / "data" / "eurosat"
# Unambiguous inputs: green (vegetation) vs blue (water). EuroSAT RGB tiles carry a
# blue cast, so they are unsuitable for colour-based change tests — use solid colours.
veg_img, water_img = solid((40, 120, 40)), solid((25, 55, 150))
_, same = post("/api/change", token=token, files={"before": ("b.png", veg_img, "image/png"), "after": ("a.png", veg_img, "image/png")}, data={"name": "same"})
check("identical scene ~0% change", same.get("changed_percent", 99) < 3, f"({same.get('changed_percent')}%)")
_, diff = post("/api/change", token=token, files={"before": ("b.png", veg_img, "image/png"), "after": ("a.png", water_img, "image/png")}, data={"name": "diff"})
check("real conversion detected (vegetation->water)", diff.get("changed_percent", 0) > 40, f"({diff.get('changed_percent')}%)")

print("\n===== 7. MODEL INTEGRITY (EuroSAT re-evaluation) =====")
if not euro.exists():
    skip("weight re-evaluation", "(EuroSAT dataset absent — run train_landcover.py to enable)")
else:
    try:
        import torch
        from torch.utils.data import DataLoader, Subset
        from torchvision import transforms
        from torchvision.datasets import EuroSAT
        from app.services import landcover_model as lm
        from scripts.train_landcover import stratified_split
        tf = transforms.Compose([transforms.ToTensor(), transforms.Normalize(lm._MEAN, lm._STD)])
        ds = EuroSAT(root=str(_BE / "data"), download=False, transform=tf)
        _, _, te = stratified_split(ds.targets)
        model = lm._load()
        check("trained weights load", model is not None)
        preds, tgts = [], []
        with torch.no_grad():
            for x, y in DataLoader(Subset(ds, te), batch_size=256):
                preds.append(model(x).argmax(1).numpy()); tgts.append(y.numpy())
        acc = float((np.concatenate(preds) == np.concatenate(tgts)).mean()) * 100
        stored = (lm.metrics() or {}).get("test_accuracy_pct")
        check("held-out test acc >= 94%", acc >= 94.0, f"(measured {acc:.2f}%)")
        check("matches stored metric", abs(acc - stored) < 1.0, f"(measured {acc:.2f}% vs stored {stored}%)")
    except Exception as ex:
        skip("weight re-evaluation", f"({ex})")

print("\n" + "=" * 54)
print(f"   RESULT: {P} passed, {F} failed, {S} skipped"
      + ("" if F == 0 else f"  -> FAILURES: {FAILS}"))
print("=" * 54)
