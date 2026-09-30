"""Quick self-test of the analysis pipeline (no server needed)."""
import io
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # Backend/

import numpy as np
from PIL import Image

from app.services import engine, segmentation, detection, change_detection, preprocessing


def make_synthetic(seed=0):
    rng = np.random.default_rng(seed)
    h, w = 400, 600
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # forest (dark green) top-left
    img[:200, :300] = (40, 100, 45) + rng.integers(-12, 12, (200, 300, 3))
    # water (blue) bottom band
    img[300:, :] = (30, 70, 150) + rng.integers(-10, 10, (100, w, 3))
    # agriculture (yellow-green) top-right
    img[:200, 300:] = (170, 180, 70) + rng.integers(-12, 12, (200, 300, 3))
    # urban (grey) middle strip with building blocks
    img[200:300, :] = (150, 150, 150) + rng.integers(-15, 15, (100, w, 3))
    for bx in range(20, 560, 80):
        img[220:270, bx:bx+45] = (200, 90, 80)  # reddish rooftops
    return np.clip(img, 0, 255).astype(np.uint8)


def to_bytes(arr):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


print("== Preprocess ==")
before = make_synthetic(1)
after = make_synthetic(2)
# introduce change: convert part of forest to urban in 'after'
after[:120, :150] = (180, 90, 80)

data_b = to_bytes(before)

pre = preprocessing.preprocess(data_b)
print("preprocessed shape:", pre.shape)

print("\n== Segmentation ==")
seg = segmentation.segment(pre)
print("land cover %:", seg.percentages)
print("confidence:", seg.confidence)
assert abs(sum(seg.percentages.values()) - 100) < 1.0, "percentages should sum ~100"

print("\n== Detection ==")
objs, counts, overlay = detection.detect_objects(pre, seg.class_map)
print("object counts:", counts, "| total:", len(objs))

print("\n== Full analyze_image (with report) ==")
doc = engine.analyze_image(data_b, "synthetic.png", owner="test-user")
print("id:", doc["id"])
print("urls:", doc["original_url"], doc["segmentation_url"], doc["detection_url"])
print("report_url:", doc.get("report_url"))
print("land_cover:", doc["land_cover"])
print("object_counts:", doc["object_counts"])
print("confidence:", doc["confidence"])

print("\n== Change detection ==")
cdoc = engine.analyze_change(to_bytes(before), to_bytes(after), "change.png", "test-user")
print("changed_percent:", cdoc["changed_percent"])
print("class_deltas:", cdoc["class_deltas"])
print("confidence:", cdoc["confidence"])

print("\n== Dynamism check (different image -> different result) ==")
seg2 = segmentation.segment(preprocessing.preprocess(to_bytes(make_synthetic(9))))
print("image A forest%:", seg.percentages["Forest"], "| image B forest%:", seg2.percentages["Forest"])

print("\nALL OK")
