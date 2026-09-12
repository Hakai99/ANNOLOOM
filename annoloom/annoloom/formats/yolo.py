"""
YOLO .txt format (bounding boxes only — YOLO's native label format has no
standard representation for polygons or keypoints in the classic detection
task file, so those shapes are skipped on export with a warning).

Line format: <class_id> <x_center> <y_center> <width> <height>
All values normalized to [0, 1] relative to image width/height.
"""

from __future__ import annotations

from pathlib import Path

from annoloom.core.shapes import ImageAnnotation, Point, Shape, ShapeType


def export_yolo(
    ann: ImageAnnotation,
    classes: list[str],
    out_path: str | Path,
    class_id_resolver=None,
) -> list[str]:
    """Write a YOLO .txt label file. Returns a list of warning strings
    for any shapes that could not be represented in YOLO format.

    class_id_resolver: optional callable(label: str) -> int. When given,
    it takes priority over `classes.index(label)` — this is how a
    user-pinned class number (e.g. always "2" for a single-species
    folder) overrides the default list-position numbering.
    """
    warnings: list[str] = []
    lines: list[str] = []

    for shape in ann.shapes:
        if shape.shape_type != ShapeType.BOX:
            warnings.append(
                f"Shape {shape.id} ({shape.shape_type.value}) skipped: "
                "YOLO detection format only supports boxes."
            )
            continue

        if class_id_resolver is not None:
            class_id = class_id_resolver(shape.label)
        elif shape.label in classes:
            class_id = classes.index(shape.label)
        else:
            warnings.append(f"Shape {shape.id}: label '{shape.label}' not in classes list, skipped.")
            continue

        x_min, y_min, x_max, y_max = shape.bounding_rect()

        x_center = ((x_min + x_max) / 2) / ann.image_width
        y_center = ((y_min + y_max) / 2) / ann.image_height
        width = (x_max - x_min) / ann.image_width
        height = (y_max - y_min) / ann.image_height

        lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

    Path(out_path).write_text("\n".join(lines) + ("\n" if lines else ""))
    return warnings


def import_yolo(
    label_path: str | Path,
    classes: list[str],
    image_path: str,
    image_width: int,
    image_height: int,
) -> ImageAnnotation:
    ann = ImageAnnotation(image_path=image_path, image_width=image_width, image_height=image_height)
    label_path = Path(label_path)
    if not label_path.exists():
        return ann

    for line in label_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            continue
        class_id, xc, yc, w, h = parts
        class_id = int(class_id)
        xc, yc, w, h = float(xc), float(yc), float(w), float(h)

        x_min = (xc - w / 2) * image_width
        y_min = (yc - h / 2) * image_height
        x_max = (xc + w / 2) * image_width
        y_max = (yc + h / 2) * image_height

        label = classes[class_id] if 0 <= class_id < len(classes) else str(class_id)
        shape = Shape(
            shape_type=ShapeType.BOX,
            label=label,
            points=[Point(x_min, y_min), Point(x_max, y_max)],
        )
        ann.add_shape(shape)

    return ann
