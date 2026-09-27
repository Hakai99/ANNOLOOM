"""
Pascal VOC .xml format (bounding boxes only, matching the original spec).
Polygon and keypoint shapes are skipped on export with a warning, same
as YOLO — VOC's <bndbox> schema has no room for them.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from xml.dom import minidom

from annoloom.core.shapes import ImageAnnotation, Point, Shape, ShapeType


def export_pascal_voc(ann: ImageAnnotation, out_path: str | Path) -> list[str]:
    warnings: list[str] = []

    root = ET.Element("annotation")
    ET.SubElement(root, "folder").text = str(Path(ann.image_path).parent.name)
    ET.SubElement(root, "filename").text = Path(ann.image_path).name
    ET.SubElement(root, "path").text = str(ann.image_path)

    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(ann.image_width)
    ET.SubElement(size, "height").text = str(ann.image_height)
    ET.SubElement(size, "depth").text = "3"

    ET.SubElement(root, "segmented").text = "0"

    for shape in ann.shapes:
        if shape.shape_type != ShapeType.BOX:
            warnings.append(
                f"Shape {shape.id} ({shape.shape_type.value}) skipped: "
                "Pascal VOC only supports boxes."
            )
            continue

        x_min, y_min, x_max, y_max = shape.bounding_rect()
        obj = ET.SubElement(root, "object")
        ET.SubElement(obj, "name").text = shape.label
        ET.SubElement(obj, "pose").text = "Unspecified"
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "1" if shape.difficult else "0"

        bnd = ET.SubElement(obj, "bndbox")
        # VOC coordinates are 1-indexed integer pixel bounds.
        ET.SubElement(bnd, "xmin").text = str(round(x_min) + 1)
        ET.SubElement(bnd, "ymin").text = str(round(y_min) + 1)
        ET.SubElement(bnd, "xmax").text = str(round(x_max) + 1)
        ET.SubElement(bnd, "ymax").text = str(round(y_max) + 1)

    rough = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(rough).toprettyxml(indent="\t")
    # Drop the extra blank lines minidom likes to add.
    pretty = "\n".join(line for line in pretty.splitlines() if line.strip())
    Path(out_path).write_text(pretty + "\n")
    return warnings


def import_pascal_voc(xml_path: str | Path) -> ImageAnnotation:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    image_path = root.findtext("path") or root.findtext("filename") or ""
    size = root.find("size")
    width = int(size.findtext("width")) if size is not None else 0
    height = int(size.findtext("height")) if size is not None else 0

    ann = ImageAnnotation(image_path=image_path, image_width=width, image_height=height)

    for obj in root.findall("object"):
        label = obj.findtext("name") or "unlabeled"
        difficult = obj.findtext("difficult") == "1"
        bnd = obj.find("bndbox")
        if bnd is None:
            continue
        # Convert back from VOC's 1-indexed bounds.
        x_min = float(bnd.findtext("xmin")) - 1
        y_min = float(bnd.findtext("ymin")) - 1
        x_max = float(bnd.findtext("xmax")) - 1
        y_max = float(bnd.findtext("ymax")) - 1

        shape = Shape(
            shape_type=ShapeType.BOX,
            label=label,
            points=[Point(x_min, y_min), Point(x_max, y_max)],
            difficult=difficult,
        )
        ann.add_shape(shape)

    return ann
