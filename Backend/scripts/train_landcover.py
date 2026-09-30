"""Train the land-cover CNN on the EuroSAT RGB benchmark.

Usage (from Backend/, venv active):
    python train_landcover.py                # full run (~10-15 min on CPU)
    python train_landcover.py --epochs 8     # quicker
    python train_landcover.py --subset 8000  # train on a subset for a fast demo build

Downloads EuroSAT (27,000 Sentinel-2 tiles, 10 land-cover classes) via torchvision,
trains a small CNN, and writes:
    models/landcover_cnn.pt        - weights (+ arch/class metadata)
    models/landcover_metrics.json  - held-out test accuracy, per-class, confusion,
                                     and the grouped 5-class accuracy the app reports.

The test split is never seen during training, so the reported accuracy is honest.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

# Make the Backend/ package root importable when run as `python scripts/train_landcover.py`
BASE = Path(__file__).resolve().parent.parent          # Backend/
sys.path.insert(0, str(BASE))

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torchvision import transforms
from torchvision.datasets import EuroSAT

from app.services.constants import CLASSES
from app.services.landcover_model import (
    EUROSAT_CLASSES, EUROSAT_TO_APP, _MEAN, _STD, build_model,
)

DATA_ROOT = BASE / "data"
WEIGHTS = BASE / "models" / "landcover_cnn.pt"
METRICS = BASE / "models" / "landcover_metrics.json"
SEED = 42


def stratified_split(targets, fracs=(0.8, 0.1, 0.1), seed=SEED):
    rng = np.random.default_rng(seed)
    targets = np.asarray(targets)
    train, val, test = [], [], []
    for c in np.unique(targets):
        idx = np.where(targets == c)[0]
        rng.shuffle(idx)
        n = len(idx)
        n_tr = int(fracs[0] * n)
        n_va = int(fracs[1] * n)
        train += idx[:n_tr].tolist()
        val += idx[n_tr:n_tr + n_va].tolist()
        test += idx[n_tr + n_va:].tolist()
    rng.shuffle(train)
    return train, val, test


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    preds, tgts = [], []
    for x, y in loader:
        x = x.to(device)
        logits = model(x)
        preds.append(logits.argmax(1).cpu().numpy())
        tgts.append(y.numpy())
    return np.concatenate(preds), np.concatenate(tgts)


def grouped(labels_10):
    """Map EuroSAT class indices -> app class indices."""
    app_idx = {c: i for i, c in enumerate(CLASSES)}
    lut = np.array([app_idx[EUROSAT_TO_APP[EUROSAT_CLASSES[i]]]
                    for i in range(len(EUROSAT_CLASSES))])
    return lut[labels_10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=14)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--subset", type=int, default=0, help="cap training images for a fast build")
    args = ap.parse_args()

    torch.manual_seed(SEED)
    device = "cpu"
    print(f"[data] downloading / loading EuroSAT into {DATA_ROOT} ...")
    t0 = time.time()

    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(64, scale=(0.75, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomRotation(20),
        transforms.ColorJitter(0.2, 0.2, 0.2),
        transforms.ToTensor(),
        transforms.Normalize(_MEAN, _STD),
        transforms.RandomErasing(p=0.2),
    ])
    eval_tf = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(_MEAN, _STD),
    ])

    ds_train = EuroSAT(root=str(DATA_ROOT), download=True, transform=train_tf)
    ds_eval = EuroSAT(root=str(DATA_ROOT), download=False, transform=eval_tf)
    targets = ds_train.targets
    print(f"[data] {len(ds_train)} images, class counts: {dict(Counter(targets))}")
    print(f"[data] EuroSAT class order: {ds_train.classes}")

    tr_idx, va_idx, te_idx = stratified_split(targets)
    if args.subset and args.subset < len(tr_idx):
        tr_idx = tr_idx[:args.subset]
    print(f"[split] train={len(tr_idx)} val={len(va_idx)} test={len(te_idx)}")

    dl_tr = DataLoader(Subset(ds_train, tr_idx), batch_size=args.batch, shuffle=True, num_workers=0)
    dl_va = DataLoader(Subset(ds_eval, va_idx), batch_size=256, shuffle=False, num_workers=0)
    dl_te = DataLoader(Subset(ds_eval, te_idx), batch_size=256, shuffle=False, num_workers=0)

    model = build_model().to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[model] small CNN, {n_params/1e3:.0f}K params")

    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    crit = nn.CrossEntropyLoss(label_smoothing=0.1)

    best_va, best_state = 0.0, None
    for ep in range(1, args.epochs + 1):
        model.train()
        te0 = time.time()
        running = 0.0
        for x, y in dl_tr:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = crit(model(x), y)
            loss.backward()
            opt.step()
            running += loss.item() * x.size(0)
        sched.step()
        vp, vt = evaluate(model, dl_va, device)
        va = float((vp == vt).mean())
        print(f"[epoch {ep:2d}/{args.epochs}] loss={running/len(tr_idx):.3f} "
              f"val_acc={va*100:.2f}% ({time.time()-te0:.0f}s)")
        if va > best_va:
            best_va, best_state = va, {k: v.cpu().clone() for k, v in model.state_dict().items()}

    # Restore best-val weights, then measure the untouched test split
    model.load_state_dict(best_state)
    tp, tt = evaluate(model, dl_te, device)
    test_acc = float((tp == tt).mean())

    # Grouped (app 5-class) accuracy
    gp, gt = grouped(tp), grouped(tt)
    grouped_acc = float((gp == gt).mean())

    # Per-app-class precision/recall + confusion
    n5 = len(CLASSES)
    conf = np.zeros((n5, n5), dtype=int)
    for a, b in zip(gt, gp):
        conf[a, b] += 1
    per_class = {}
    for i, c in enumerate(CLASSES):
        tp_i = conf[i, i]
        recall = tp_i / conf[i].sum() if conf[i].sum() else None
        prec = tp_i / conf[:, i].sum() if conf[:, i].sum() else None
        per_class[c] = {
            "support": int(conf[i].sum()),
            "recall_pct": round(100 * recall, 1) if recall is not None else None,
            "precision_pct": round(100 * prec, 1) if prec is not None else None,
        }

    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(),
                "eurosat_classes": EUROSAT_CLASSES,
                "app_classes": CLASSES}, WEIGHTS)

    out = {
        "dataset": "EuroSAT RGB (Sentinel-2, 10 classes)",
        "backbone": "3-block CNN + global average pooling",
        "n_params_k": round(n_params / 1e3),
        "n_train": len(tr_idx), "n_val": len(va_idx), "n_test": len(te_idx),
        "epochs": args.epochs,
        "test_accuracy_pct": round(100 * test_acc, 2),
        "grouped_accuracy_pct": round(100 * grouped_acc, 2),
        "best_val_accuracy_pct": round(100 * best_va, 2),
        "app_classes": CLASSES,
        "per_class": per_class,
        "confusion_app": conf.tolist(),
        "eurosat_to_app": EUROSAT_TO_APP,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    METRICS.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("\n================  RESULTS  ================")
    print(f"  10-class test accuracy : {100*test_acc:.2f}%")
    print(f"  5-class (app) accuracy : {100*grouped_acc:.2f}%")
    print(f"  weights -> {WEIGHTS}")
    print(f"  metrics -> {METRICS}")
    print(f"  total time: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
