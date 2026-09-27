"""
AnnoLoom's native .aloom.json sidecar format. Stores every field exactly
(box, polygon, keypoints, skeleton, difficult, group_id) with no lossy
conversion — this is the format the app autosaves in, while YOLO/VOC/COCO
are used only for export to other tools.
"""

from __future__ import annotations

import json
from pathlib import Path

from annoloom.core.shapes import ImageAnnotation, Keypoint, Point, Shape, ShapeType


def _shape_to_dict(shape: Shape) -> dict:
    return {
        "id": shape.id,
        "shape_type": shape.shape_type.value,
        "label": shape.label,
        "points": [p.as_tuple() for p in shape.points],
        "keypoints": [
            {"point": kp.point.as_tuple(), "label": kp.label, "visible": kp.visible}
            for kp in shape.keypoints
        ],
        "skeleton": shape.skeleton,
        "difficult": shape.difficult,
        "group_id": shape.group_id,
    }


def _shape_from_dict(d: dict) -> Shape:
    return Shape(
        shape_type=ShapeType(d["shape_type"]),
        label=d["label"],
        id=d.get("id") or Shape.__dataclass_fields__["id"].default_factory(),
        points=[Point(x, y) for x, y in d.get("points", [])],
        keypoints=[
            Keypoint(point=Point(*kp["point"]), label=kp["label"], visible=kp.get("visible", True))
            for kp in d.get("keypoints", [])
        ],
        skeleton=[tuple(pair) for pair in d.get("skeleton", [])],
        difficult=d.get("difficult", False),
        group_id=d.get("group_id"),
    )


def save_native(ann: ImageAnnotation, out_path: str | Path) -> None:
    data = {
        "image_path": ann.image_path,
        "image_width": ann.image_width,
        "image_height": ann.image_height,
        "shapes": [_shape_to_dict(s) for s in ann.shapes],
    }
    Path(out_path).write_text(json.dumps(data, indent=2))


def load_native(path: str | Path) -> ImageAnnotation:
    data = json.loads(Path(path).read_text())
    ann = ImageAnnotation(
        image_path=data["image_path"],
        image_width=data["image_width"],
        image_height=data["image_height"],
    )
    for shape_dict in data.get("shapes", []):
        ann.shapes.append(_shape_from_dict(shape_dict))
    return ann
