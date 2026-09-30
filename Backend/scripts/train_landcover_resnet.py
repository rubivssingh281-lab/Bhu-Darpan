"""Train the ResNet-lite land-cover model on EuroSAT RGB and promote it only if it beats
the current model on the SAME held-out test split.

Usage (from Backend/, venv active):
    python scripts/train_landcover_resnet.py                 # full run
    python scripts/train_landcover_resnet.py --epochs 12     # quicker

Why it is stronger than the baseline 3-block CNN at the same compute budget:
  * compact 4-stage ResNet (17 conv layers, residual connections)
  * images pre-loaded as tensors + vectorised batch augmentation (fast on CPU)
  * dihedral augmentation (8 rotations/flips — overhead imagery has no "up"),
    reflect-pad random crops, brightness/contrast jitter and CutMix
  * SGD-Nesterov with a OneCycle schedule, label smoothing, and an EMA of the weights
  * 8-way dihedral test-time augmentation (TTA) at evaluation

The test split (seed 42, stratified 80/10/10 — identical to train_landcover.py) is never
seen during training or model selection, so the comparison with the current model is fair.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # Backend/
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.datasets import EuroSAT

from app.services.constants import CLASSES
from app.services.landcover_model import EUROSAT_CLASSES, EUROSAT_TO_APP, _MEAN, _STD, build_model
from train_landcover import SEED, grouped, stratified_split

DATA_ROOT = BASE / "data"
MODELS = BASE / "models"
WEIGHTS = MODELS / "landcover_cnn.pt"
METRICS = MODELS / "landcover_metrics.json"
CAND_W = MODELS / "landcover_cnn_candidate.pt"
CAND_M = MODELS / "landcover_metrics_candidate.json"


def log(*a):
    print(*a, flush=True)


def load_tensors():
    ds = EuroSAT(root=str(DATA_ROOT), download=False)
    X = np.empty((len(ds), 64, 64, 3), dtype=np.uint8)
    for i in range(len(ds)):
        X[i] = np.asarray(ds[i][0].convert("RGB").resize((64, 64)))
    return torch.from_numpy(X).permute(0, 3, 1, 2).contiguous(), np.asarray(ds.targets)


MEAN = torch.tensor(_MEAN).view(1, 3, 1, 1)
STD = torch.tensor(_STD).view(1, 3, 1, 1)


def norm(xb_u8):
    return (xb_u8.float() / 255.0 - MEAN) / STD


def dihedral(x, k, flip):
    x = torch.rot90(x, k, dims=(2, 3))
    return torch.flip(x, dims=(3,)) if flip else x


def augment(xb):
    """Vectorised per-sample augmentation on a uint8 batch (N,3,64,64) -> float normalised."""
    n = xb.size(0)
    x = xb.float() / 255.0
    # dihedral group: random rot90 × horizontal flip, per sample (8 groups)
    out = torch.empty_like(x)
    ks = torch.randint(0, 4, (n,))
    fl = torch.rand(n) < 0.5
    for k in range(4):
        for f in (False, True):
            m = (ks == k) & (fl == f)
            if m.any():
                out[m] = dihedral(x[m], k, f)
    x = out
    # reflect-pad 6 + random 64x64 crop (translation jitter)
    x = F.pad(x, (6, 6, 6, 6), mode="reflect")
    ox, oy = torch.randint(0, 13, (n,)), torch.randint(0, 13, (n,))
    x = torch.stack([x[i, :, oy[i]:oy[i] + 64, ox[i]:ox[i] + 64] for i in range(n)])
    # brightness / contrast jitter (±15%)
    b = 1 + (torch.rand(n, 1, 1, 1) - 0.5) * 0.3
    c = 1 + (torch.rand(n, 1, 1, 1) - 0.5) * 0.3
    mu = x.mean(dim=(1, 2, 3), keepdim=True)
    x = ((x - mu) * c + mu) * b
    x = x.clamp(0, 1)
    return (x - MEAN) / STD


def cutmix(x, y, n_cls, alpha=1.0):
    lam = float(np.random.beta(alpha, alpha))
    idx = torch.randperm(x.size(0))
    H = W = x.size(2)
    rh, rw = int(H * math.sqrt(1 - lam)), int(W * math.sqrt(1 - lam))
    cy, cx = np.random.randint(H), np.random.randint(W)
    y0, y1 = max(cy - rh // 2, 0), min(cy + rh // 2, H)
    x0, x1 = max(cx - rw // 2, 0), min(cx + rw // 2, W)
    x = x.clone()
    x[:, :, y0:y1, x0:x1] = x[idx, :, y0:y1, x0:x1]
    lam = 1 - ((y1 - y0) * (x1 - x0) / (H * W))
    y1h = F.one_hot(y, n_cls).float()
    return x, lam * y1h + (1 - lam) * y1h[idx]


@torch.no_grad()
def predict(model, X_u8, tta=1, bs=512):
    """tta: 1 = plain, 4 = four rotations, 8 = full dihedral group."""
    model.eval()
    outs = []
    views = {1: [(0, False)], 4: [(k, False) for k in range(4)],
             8: [(k, f) for k in range(4) for f in (False, True)]}[tta]
    for i in range(0, X_u8.size(0), bs):
        x = norm(X_u8[i:i + bs])
        outs.append(sum(F.softmax(model(dihedral(x, k, f)), 1) for k, f in views) / len(views))
    return torch.cat(outs)


class EMA:
    """Exponential moving average of the weights with a warm-up schedule
    (decay = min(max_decay, (1+n)/(10+n))), so the average is not dominated by the random
    initialisation during the early, high-learning-rate phase."""
    def __init__(self, model, decay=0.999):
        self.m = copy.deepcopy(model).eval()
        self.max_decay = decay
        self.n = 0

    @torch.no_grad()
    def update(self, model):
        self.n += 1
        d = min(self.max_decay, (1 + self.n) / (10 + self.n))
        for (k, v), (_, s) in zip(self.m.state_dict().items(), model.state_dict().items()):
            if v.dtype.is_floating_point:
                v.mul_(d).add_(s.detach(), alpha=1 - d)
            else:
                v.copy_(s)


def metrics_block(pred10, tgt10):
    acc10 = float((pred10 == tgt10).mean())
    gp, gt = grouped(pred10), grouped(tgt10)
    acc5 = float((gp == gt).mean())
    n5 = len(CLASSES)
    conf = np.zeros((n5, n5), dtype=int)
    for a, b in zip(gt, gp):
        conf[a, b] += 1
    per = {}
    for i, c in enumerate(CLASSES):
        tp = conf[i, i]
        rec = tp / conf[i].sum() if conf[i].sum() else None
        pre = tp / conf[:, i].sum() if conf[:, i].sum() else None
        per[c] = {"support": int(conf[i].sum()),
                  "recall_pct": round(100 * rec, 1) if rec is not None else None,
                  "precision_pct": round(100 * pre, 1) if pre is not None else None}
    return acc10, acc5, per, conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=0.2)
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--no-promote", action="store_true")
    a = ap.parse_args()

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    torch.set_num_threads(a.threads)
    t0 = time.time()

    log("[data] loading EuroSAT into memory ...")
    X, y = load_tensors()
    tr, va, te = stratified_split(y)
    Xtr, ytr = X[tr], torch.from_numpy(y[tr]).long()
    Xva, yva = X[va], y[va]
    Xte, yte = X[te], y[te]
    log(f"[data] train={len(tr)} val={len(va)} test={len(te)}  ({time.time()-t0:.0f}s)")

    model = build_model("resnet_lite")
    n_params = sum(p.numel() for p in model.parameters())
    log(f"[model] resnet_lite, {n_params/1e6:.2f}M params")
    ema = EMA(model, decay=0.999)

    steps_per_ep = math.ceil(len(tr) / a.batch)
    opt = torch.optim.SGD(model.parameters(), lr=a.lr, momentum=0.9, nesterov=True, weight_decay=5e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.epochs * steps_per_ep,
                                                pct_start=0.15, div_factor=20, final_div_factor=200)
    n_cls = len(EUROSAT_CLASSES)

    best_va, best_state, best_ep = -1.0, None, 0
    for ep in range(1, a.epochs + 1):
        model.train()
        e0 = time.time()
        perm = torch.randperm(len(tr))
        running = 0.0
        for s in range(steps_per_ep):
            idx = perm[s * a.batch:(s + 1) * a.batch]
            xb = augment(Xtr[idx])
            yb = ytr[idx]
            if np.random.rand() < 0.5:                       # CutMix half the batches
                xb, ysoft = cutmix(xb, yb, n_cls)
            else:
                ysoft = F.one_hot(yb, n_cls).float() * 0.9 + 0.1 / n_cls   # label smoothing
            loss = torch.sum(-ysoft * F.log_softmax(model(xb), 1), 1).mean()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            ema.update(model)
            running += loss.item()
        # score both the raw weights and the EMA; keep whichever validates best
        va_raw = float((predict(model, Xva).argmax(1).numpy() == yva).mean())
        va_ema = float((predict(ema.m, Xva).argmax(1).numpy() == yva).mean())
        va_acc, src = (va_ema, ema.m) if va_ema >= va_raw else (va_raw, model)
        if va_acc > best_va:
            best_va, best_ep = va_acc, ep
            best_state = {k: v.clone() for k, v in src.state_dict().items()}
        log(f"[epoch {ep:2d}/{a.epochs}] loss={running/steps_per_ep:.3f} val raw={va_raw*100:.2f}% "
            f"ema={va_ema*100:.2f}% best={best_va*100:.2f}%@{best_ep} "
            f"({time.time()-e0:.0f}s, lr={sched.get_last_lr()[0]:.4f})")

    final = build_model("resnet_lite")
    final.load_state_dict(best_state)
    p_plain = predict(final, Xte, tta=1).argmax(1).numpy()
    p_tta = predict(final, Xte, tta=4).argmax(1).numpy()
    p_tta8 = predict(final, Xte, tta=8).argmax(1).numpy()
    acc10, acc5, per, conf = metrics_block(p_plain, yte)
    acc10_t, acc5_t, per_t, conf_t = metrics_block(p_tta, yte)
    acc10_8, acc5_8, _, _ = metrics_block(p_tta8, yte)
    log(f"\n[test] plain: 10-class {acc10*100:.2f}% | grouped {acc5*100:.2f}%")
    log(f"[test] TTA×4: 10-class {acc10_t*100:.2f}% | grouped {acc5_t*100:.2f}%")
    log(f"[test] TTA×8: 10-class {acc10_8*100:.2f}% | grouped {acc5_8*100:.2f}%")

    # the app runs inference with 4-way rotation TTA, so that is the model's reported accuracy
    out = {
        "dataset": "EuroSAT RGB (Sentinel-2, 10 classes)",
        "backbone": "ResNet-lite (4 stages, 17 conv layers, residual) + GAP",
        "arch": "resnet_lite",
        "n_params_k": round(n_params / 1e3),
        "n_train": len(tr), "n_val": len(va), "n_test": len(te),
        "epochs": a.epochs, "best_epoch": best_ep,
        "recipe": "SGD-Nesterov OneCycle, label smoothing 0.1, CutMix, dihedral+crop+jitter aug, EMA 0.999",
        "tta": "4-way rotation (0/90/180/270°) — as used by the app at inference",
        "test_accuracy_pct": round(100 * acc10_t, 2),
        "grouped_accuracy_pct": round(100 * acc5_t, 2),
        "test_accuracy_no_tta_pct": round(100 * acc10, 2),
        "grouped_accuracy_no_tta_pct": round(100 * acc5, 2),
        "test_accuracy_tta8_pct": round(100 * acc10_8, 2),
        "grouped_accuracy_tta8_pct": round(100 * acc5_8, 2),
        "best_val_accuracy_pct": round(100 * best_va, 2),
        "app_classes": CLASSES,
        "per_class": per_t,
        "confusion_app": conf_t.tolist(),
        "eurosat_to_app": EUROSAT_TO_APP,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "train_seconds": round(time.time() - t0),
    }
    torch.save({"arch": "resnet_lite", "state_dict": final.state_dict(), "tta": 4,
                "eurosat_classes": EUROSAT_CLASSES, "app_classes": CLASSES}, CAND_W)
    CAND_M.write_text(json.dumps(out, indent=2), encoding="utf-8")

    cur = json.loads(METRICS.read_text(encoding="utf-8")) if METRICS.exists() else {}
    cur10, cur5 = cur.get("test_accuracy_pct", 0), cur.get("grouped_accuracy_pct", 0)
    log(f"\n[compare] current : 10-class {cur10}% | grouped {cur5}%")
    log(f"[compare] candidate: 10-class {out['test_accuracy_pct']}% | grouped {out['grouped_accuracy_pct']}%")
    better = (out["test_accuracy_pct"], out["grouped_accuracy_pct"]) > (cur10, cur5)
    if better and not a.no_promote:
        shutil.copy2(WEIGHTS, MODELS / "landcover_cnn_prev.pt")
        shutil.copy2(METRICS, MODELS / "landcover_metrics_prev.json")
        shutil.copy2(CAND_W, WEIGHTS)
        shutil.copy2(CAND_M, METRICS)
        log("[promote] candidate is better -> promoted (previous model backed up as *_prev)")
    else:
        log("[promote] candidate NOT better -> current model kept")
    log(f"[done] total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
