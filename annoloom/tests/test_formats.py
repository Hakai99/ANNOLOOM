import tempfile
from pathlib import Path

from annoloom.core.shapes import ImageAnnotation, Point, Shape, ShapeType, Keypoint
from annoloom.formats.native import save_native, load_native
from annoloom.formats.yolo import export_yolo, import_yolo
from annoloom.formats.pascal_voc import export_pascal_voc, import_pascal_voc
from annoloom.formats.coco import export_coco, import_coco


def make_sample_annotation() -> ImageAnnotation:
    ann = ImageAnnotation(image_path="cat.jpg", image_width=640, image_height=480)
    ann.add_shape(Shape(
        shape_type=ShapeType.BOX,
        label="cat",
        points=[Point(10, 20), Point(110, 220)],
    ))
    ann.add_shape(Shape(
        shape_type=ShapeType.POLYGON,
        label="tail",
        points=[Point(200, 200), Point(250, 210), Point(230, 260)],
    ))
    ann.add_shape(Shape(
        shape_type=ShapeType.KEYPOINTS,
        label="pose",
        keypoints=[
            Keypoint(Point(100, 100), "nose"),
            Keypoint(Point(90, 120), "left_eye"),
        ],
        skeleton=[(0, 1)],
    ))
    return ann


def test_native_roundtrip():
    ann = make_sample_annotation()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "cat.aloom.json"
        save_native(ann, path)
        loaded = load_native(path)

    assert loaded.image_width == 640
    assert len(loaded.shapes) == 3
    box = [s for s in loaded.shapes if s.shape_type == ShapeType.BOX][0]
    assert box.points[0].x == 10
    assert box.points[1].y == 220
    kp_shape = [s for s in loaded.shapes if s.shape_type == ShapeType.KEYPOINTS][0]
    assert len(kp_shape.keypoints) == 2
    assert kp_shape.skeleton == [(0, 1)]
    print("native roundtrip OK")


def test_yolo_export_import():
    ann = make_sample_annotation()
    classes = ["cat", "tail", "pose"]
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "cat.txt"
        warnings = export_yolo(ann, classes, path)
        assert len(warnings) == 2  # polygon + keypoints skipped
        content = path.read_text().strip()
        assert content.startswith("0 ")  # class_id 0 = cat

        reimported = import_yolo(path, classes, "cat.jpg", 640, 480)
        assert len(reimported.shapes) == 1
        box = reimported.shapes[0]
        assert abs(box.points[0].x - 10) < 0.5
        assert abs(box.points[1].y - 220) < 0.5
    print("yolo export/import OK, warnings:", warnings)


def test_pascal_voc_export_import():
    ann = make_sample_annotation()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "cat.xml"
        warnings = export_pascal_voc(ann, path)
        assert len(warnings) == 2

        reimported = import_pascal_voc(path)
        assert len(reimported.shapes) == 1
        box = reimported.shapes[0]
        # VOC uses 1-indexed ints; expect close to original after round trip
        assert abs(box.points[0].x - 10) < 1.5
        assert abs(box.points[1].y - 220) < 1.5
    print("pascal voc export/import OK, warnings:", warnings)


def test_coco_export_import_full_fidelity():
    ann = make_sample_annotation()
    classes = ["cat", "tail", "pose"]
    with tempfile.TemporaryDirectory() as d:
        json_path = Path(d) / "annotations.json"
        export_coco([ann], classes, json_path)

        reimported = import_coco(json_path, image_dir=d)
        assert len(reimported) == 1
        shapes = reimported[0].shapes
        assert len(shapes) == 3  # box, polygon, AND keypoints preserved

        poly = [s for s in shapes if s.shape_type == ShapeType.POLYGON][0]
        assert len(poly.points) == 3

        kp = [s for s in shapes if s.shape_type == ShapeType.KEYPOINTS][0]
        assert len(kp.keypoints) == 2
    print("coco export/import full fidelity OK (no warnings needed)")


def test_shape_validation_rejects_bad_box():
    with_bad = Shape(shape_type=ShapeType.BOX, label="x", points=[Point(0, 0)])
    try:
        with_bad.validate()
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("shape validation correctly rejects malformed box")


if __name__ == "__main__":
    test_native_roundtrip()
    test_yolo_export_import()
    test_pascal_voc_export_import()
    test_coco_export_import_full_fidelity()
    test_shape_validation_rejects_bad_box()
    print("\nAll tests passed.")
