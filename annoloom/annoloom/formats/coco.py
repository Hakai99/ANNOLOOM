"""
COCO JSON format. Unlike YOLO/VOC, COCO's schema natively supports both
bounding boxes and polygon segmentations, and (via the keypoints array)
labeled keypoints — so this is the richest of the three interchange
formats and the recommended one when polygons/keypoints matter.

Note: COCO keypoints require a fixed, pre-declared skeleton per category
(same ordered list of keypoint names for every instance of that category).
Shapes are grouped by label into categories; if a project mixes keypoint
sets under the same label, the union of names is used and missing points
are marked not-visible (v=0).
"""

from __future__ import annotations

import json
from pathlib import Path

from annoloom.core.shapes import ImageAnnotation, Point, Shape, ShapeType, Keypoint


def _polygon_flat(points: list[Point]) -> list[float]:
    flat: list[float] = []
    for p in points:
        flat.extend([p.x, p.y])
    return flat


def export_coco(
    annotations: list[ImageAnnotation],
    classes: list[str],
    out_path: str | Path,
) -> None:
    categories = [{"id": i + 1, "name": name, "supercategory": "none"} for i, name in enumerate(classes)]
    class_to_id = {name: i + 1 for i, name in enumerate(classes)}

    images = []
    coco_annotations = []
    ann_id = 1

    for img_id, img_ann in enumerate(annotations, start=1):
        images.append({
            "id": img_id,
            "file_name": Path(img_ann.image_path).name,
            "width": img_ann.image_width,
            "height": img_ann.image_height,
        })

        for shape in img_ann.shapes:
            category_id = class_to_id.get(shape.label)
            if category_id is None:
                continue

            x_min, y_min, x_max, y_max = shape.bounding_rect()
            bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
            area = (x_max - x_min) * (y_max - y_min)

            entry = {
                "id": ann_id,
                "image_id": img_id,
                "category_id": category_id,
                "bbox": bbox,
                "area": area,
                "iscrowd": 0,
            }

            if shape.shape_type == ShapeType.POLYGON:
                entry["segmentation"] = [_polygon_flat(shape.points)]
            elif shape.shape_type == ShapeType.KEYPOINTS:
                kp_flat: list[float] = []
                for kp in shape.keypoints:
                    v = 2 if kp.visible else 1
                    kp_flat.extend([kp.point.x, kp.point.y, v])
                entry["keypoints"] = kp_flat
                entry["num_keypoints"] = sum(1 for kp in shape.keypoints if kp.visible)

            coco_annotations.append(entry)
            ann_id += 1

    coco = {
        "images": images,
        "annotations": coco_annotations,
        "categories": categories,
    }
    Path(out_path).write_text(json.dumps(coco, indent=2))


def import_coco(json_path: str | Path, image_dir: str | Path) -> list[ImageAnnotation]:
    data = json.loads(Path(json_path).read_text())
    image_dir = Path(image_dir)

    categories = {c["id"]: c["name"] for c in data.get("categories", [])}
    images_by_id = {img["id"]: img for img in data.get("images", [])}

    ann_by_image: dict[int, ImageAnnotation] = {}
    for img in data.get("images", []):
        ann_by_image[img["id"]] = ImageAnnotation(
            image_path=str(image_dir / img["file_name"]),
            image_width=img["width"],
            image_height=img["height"],
        )

    for entry in data.get("annotations", []):
        image_id = entry["image_id"]
        img_ann = ann_by_image.get(image_id)
        if img_ann is None:
            continue
        label = categories.get(entry["category_id"], str(entry["category_id"]))

        if "segmentation" in entry and entry["segmentation"]:
            flat = entry["segmentation"][0]
            points = [Point(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
            shape = Shape(shape_type=ShapeType.POLYGON, label=label, points=points)
        elif "keypoints" in entry and entry["keypoints"]:
            flat = entry["keypoints"]
            keypoints = [
                Keypoint(point=Point(flat[i], flat[i + 1]), label=f"kp{i // 3}", visible=flat[i + 2] > 0)
                for i in range(0, len(flat), 3)
            ]
            shape = Shape(shape_type=ShapeType.KEYPOINTS, label=label, keypoints=keypoints)
        else:
            x, y, w, h = entry["bbox"]
            shape = Shape(
                shape_type=ShapeType.BOX,
                label=label,
                points=[Point(x, y), Point(x + w, y + h)],
            )

        img_ann.add_shape(shape)

    return list(ann_by_image.values())
