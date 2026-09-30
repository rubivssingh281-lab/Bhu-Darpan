"""Disaster-scene classifier — reproducible transfer-learning pipeline (ROADMAP).

Status: SCAFFOLD, not trained in this repo. The live app runs the operational detector in
app/services/disaster.py (EuroSAT CNN 95.89% + NIR/SWIR indices). Run this when a labelled
dataset + (ideally) a GPU are available, then point disaster.py at models/disaster_cnn.pt.

ACCURACY STRATEGY (highest feasible on a single GPU):
  * Transfer learning from an ImageNet-pretrained backbone (EfficientNet-B0 default, or
    ResNet50 / ConvNeXt) — reaches ~90-95% on AIDER-style 5-class emergency imagery, far
    above a from-scratch CNN. `--backbone scratch` keeps a dependency-free fallback.
  * Two-phase fine-tune: warm up the new head (backbone frozen), then unfreeze at a low LR.
  * Regularisation: label smoothing, MixUp, heavy augmentation, class-balanced sampling.
  * Selection by macro-F1 (imbalance-robust); test-time augmentation (TTA) at evaluation.
  * AMP mixed precision + cosine schedule + early stopping.

--------------------------------------------------------------------------------
DATASETS (download separately — large, not bundled)
  * AIDER  — fire / flood / collapsed_building / traffic_incident / normal
             https://github.com/ckyrkou/AIDER
  * xView2 / xBD — building damage (none/minor/major/destroyed), pre/post
             https://xview2.org
  * FloodNet / Sen1Floods11 — flood segmentation (optical + SAR)
Layout (ImageFolder):  data/disaster/{train,val,test}/<class>/*.jpg
USAGE:  cd Backend && python -m scripts.train_disaster --data data/disaster --backbone effnet
Outputs: models/disaster_cnn.pt  +  models/disaster_metrics.json
--------------------------------------------------------------------------------
FULL-SPEC ROADMAP: swap the encoder for an EO foundation model (Prithvi-EO-2.0 / SatMAE /
Scale-MAE); add Mask2Former/SegFormer (extent) + ChangeFormer/Siamese-UNet (pre/post);
fuse optical+SAR+thermal via cross-attention; MC-dropout/evidential uncertainty + ECE
calibration; exposure = population/structure proxy over the impact mask (never person ID).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
WEIGHTS = BASE / "models" / "disaster_cnn.pt"
METRICS = BASE / "models" / "disaster_metrics.json"


def build_model(backbone: str, n_classes: int):
    """Pretrained backbone with a fresh classifier head, or a compact from-scratch CNN."""
    import torch.nn as nn

    if backbone == "scratch":
        def blk(ci, co):
            return nn.Sequential(nn.Conv2d(ci, co, 3, padding=1), nn.BatchNorm2d(co),
                                 nn.ReLU(inplace=True), nn.MaxPool2d(2))
        return nn.Sequential(blk(3, 32), blk(32, 64), blk(64, 128), blk(128, 256),
                             nn.AdaptiveAvgPool2d(1), nn.Flatten(),
                             nn.Dropout(0.3), nn.Linear(256, n_classes)), []

    from torchvision import models
    if backbone == "resnet50":
        m = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
        m.fc = nn.Linear(m.fc.in_features, n_classes); head = list(m.fc.parameters())
    elif backbone == "convnext":
        m = models.convnext_tiny(weights=models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1)
        m.classifier[2] = nn.Linear(m.classifier[2].in_features, n_classes); head = list(m.classifier[2].parameters())
    else:  # effnet (default)
        m = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, n_classes); head = list(m.classifier[1].parameters())
    return m, head


def _metrics(y_true, y_pred, n):
    import numpy as np
    yt, yp = np.asarray(y_true), np.asarray(y_pred)
    cm = np.zeros((n, n), int)
    for t, p in zip(yt, yp):
        cm[t, p] += 1
    tp = np.diag(cm).astype(float)
    prec = tp / (cm.sum(0) + 1e-9)
    rec = tp / (cm.sum(1) + 1e-9)
    f1 = 2 * prec * rec / (prec + rec + 1e-9)
    iou = tp / (cm.sum(0) + cm.sum(1) - tp + 1e-9)
    return {"accuracy": round(float((yt == yp).mean()) * 100, 2),
            "macro_f1": round(float(f1.mean()) * 100, 2),
            "mean_iou": round(float(iou.mean()) * 100, 2),
            "per_class_f1": [round(float(x) * 100, 2) for x in f1],
            "confusion_matrix": cm.tolist()}


def _mixup(x, y, n_classes, alpha=0.2):
    import numpy as np, torch
    lam = np.random.beta(alpha, alpha)
    idx = torch.randperm(x.size(0), device=x.device)
    yh = torch.zeros(x.size(0), n_classes, device=x.device).scatter_(1, y.view(-1, 1), 1.0)
    return lam * x + (1 - lam) * x[idx], lam * yh + (1 - lam) * yh[idx]


def _evaluate(model, loader, dev, n_classes, tta=True):
    import torch
    model.eval(); yt, yp = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(dev)
            logit = model(x)
            if tta:
                logit = logit + model(torch.flip(x, dims=[3]))   # horizontal-flip TTA
            yp += logit.argmax(1).cpu().tolist(); yt += y.tolist()
    return _metrics(yt, yp, n_classes)


def train(a):
    import numpy as np, torch
    from torch.utils.data import DataLoader, WeightedRandomSampler
    from torchvision import datasets, transforms

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    root = Path(a.data)
    if not (root / "train").exists():
        raise SystemExit(f"Dataset not found at {root}/train. See the docstring for AIDER/xView2 links.")

    norm = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    tf_tr = transforms.Compose([
        transforms.Resize((a.img, a.img)), transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(), transforms.RandomRotation(20),
        transforms.ColorJitter(0.25, 0.25, 0.25), transforms.RandAugment(),
        transforms.ToTensor(), norm,
        transforms.RandomErasing(p=0.25)])
    tf_ev = transforms.Compose([transforms.Resize((a.img, a.img)), transforms.ToTensor(), norm])

    tr = datasets.ImageFolder(root / "train", tf_tr)
    va = datasets.ImageFolder(root / "val", tf_ev)
    te = datasets.ImageFolder(root / "test", tf_ev) if (root / "test").exists() else None
    classes = tr.classes
    nC = len(classes)

    # class-balanced sampling for the heavy 'normal' vs rare-disaster imbalance
    counts = np.bincount([y for _, y in tr.samples], minlength=nC)
    sw = [1.0 / counts[y] for _, y in tr.samples]
    sampler = WeightedRandomSampler(sw, len(sw), replacement=True)
    trl = DataLoader(tr, batch_size=a.batch, sampler=sampler, num_workers=a.workers, pin_memory=True)
    val = DataLoader(va, batch_size=a.batch, num_workers=a.workers, pin_memory=True)

    model, head_params = build_model(a.backbone, nC)
    model = model.to(dev)
    lossf = torch.nn.CrossEntropyLoss(label_smoothing=0.1)
    scaler = torch.cuda.amp.GradScaler(enabled=(dev == "cuda"))

    def run_phase(params, lr, epochs, tag):
        nonlocal best
        opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs))
        for ep in range(1, epochs + 1):
            model.train()
            for x, y in trl:
                x, y = x.to(dev), y.to(dev)
                opt.zero_grad()
                with torch.cuda.amp.autocast(enabled=(dev == "cuda")):
                    if a.mixup:
                        xm, ys = _mixup(x, y, nC)
                        loss = torch.sum(-ys * torch.log_softmax(model(xm), 1), 1).mean()
                    else:
                        loss = lossf(model(x), y)
                scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            sched.step()
            m = _evaluate(model, val, dev, nC, tta=a.tta)
            print(f"[{tag}] ep {ep:02d}  acc {m['accuracy']}%  macroF1 {m['macro_f1']}%  mIoU {m['mean_iou']}%")
            if m["macro_f1"] > best["macro_f1"]:
                best = m; best["classes"] = classes
                torch.save({"state_dict": model.state_dict(), "classes": classes,
                            "img": a.img, "backbone": a.backbone}, WEIGHTS)
                stale[0] = 0
            else:
                stale[0] += 1
                if a.patience and stale[0] >= a.patience:
                    print(f"[{tag}] early stop (no macro-F1 gain in {a.patience})"); return

    best = {"macro_f1": -1.0, "accuracy": 0.0, "mean_iou": 0.0}
    stale = [0]
    if a.backbone != "scratch" and head_params:
        for p in model.parameters():
            p.requires_grad = False
        for p in head_params:
            p.requires_grad = True
        run_phase(head_params, a.lr, a.warmup, "head")          # phase 1: train head only
        for p in model.parameters():
            p.requires_grad = True
    run_phase(model.parameters(), a.lr * 0.1 if a.backbone != "scratch" else a.lr,
              a.epochs, "finetune")                             # phase 2: full fine-tune

    out = {**best, "epochs": a.epochs, "backbone": a.backbone}
    if te is not None:                                          # final held-out test
        model.load_state_dict(torch.load(WEIGHTS, map_location=dev)["state_dict"])
        out["test"] = _evaluate(model, DataLoader(te, batch_size=a.batch, num_workers=a.workers), dev, nC, tta=a.tta)
        print("TEST:", out["test"])
    METRICS.write_text(json.dumps(out, indent=2))
    print(f"\nBest val macro-F1 {best['macro_f1']}% · acc {best['accuracy']}% -> {WEIGHTS}")
    if best["accuracy"] < 85:
        print("NOTE: below 85% — add data/epochs, try --backbone resnet50/convnext, or a pretrained EO backbone.")


if __name__ == "__main__":
    import torch  # noqa: E402
    ap = argparse.ArgumentParser(description="Train the disaster-scene classifier (transfer learning).")
    ap.add_argument("--data", default="data/disaster")
    ap.add_argument("--backbone", default="effnet", choices=["effnet", "resnet50", "convnext", "scratch"])
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--warmup", type=int, default=3, help="head-only warm-up epochs before unfreezing")
    ap.add_argument("--img", type=int, default=224)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--mixup", action="store_true", default=True)
    ap.add_argument("--tta", action="store_true", default=True)
    train(ap.parse_args())
