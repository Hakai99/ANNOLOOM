"""
Core annotation data model for AnnoLoom.

All coordinates are stored as floats internally (image pixel space) and
converted to the correct type only at the point of use (e.g. drawing
with QPainter requires ints; export formats may require normalized
floats). This avoids the classic float/int mismatch bugs that plague
older Qt-based annotation tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class ShapeType(str, Enum):
    BOX = "box"
    POLYGON = "polygon"
    KEYPOINTS = "keypoints"


@dataclass
class Point:
    x: float
    y: float

    def as_int_tuple(self) -> tuple[int, int]:
        """Round to the nearest pixel. Use this — never int() truncation —
        anywhere a Qt drawing call needs integer coordinates."""
        return (round(self.x), round(self.y))

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Keypoint:
    point: Point
    label: str
    visible: bool = True


@dataclass
class Shape:
    """A single annotated shape belonging to one image."""

    shape_type: ShapeType
    label: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # BOX: exactly two points (top-left, bottom-right)
    # POLYGON: three or more points, in order
    points: list[Point] = field(default_factory=list)

    # KEYPOINTS: named, individually-visible points (e.g. pose skeletons)
    keypoints: list[Keypoint] = field(default_factory=list)

    # Optional skeleton edges for keypoint shapes, as (index_a, index_b) pairs,
    # used only for drawing connective lines between keypoints.
    skeleton: list[tuple[int, int]] = field(default_factory=list)

    difficult: bool = False
    group_id: Optional[int] = None

    def bounding_rect(self) -> tuple[float, float, float, float]:
        """Return (x_min, y_min, x_max, y_max) covering this shape."""
        if self.shape_type == ShapeType.KEYPOINTS:
            xs = [kp.point.x for kp in self.keypoints]
            ys = [kp.point.y for kp in self.keypoints]
        else:
            xs = [p.x for p in self.points]
            ys = [p.y for p in self.points]
        if not xs or not ys:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))

    def validate(self) -> None:
        if self.shape_type == ShapeType.BOX and len(self.points) != 2:
            raise ValueError(f"Box shape {self.id} must have exactly 2 points")
        if self.shape_type == ShapeType.POLYGON and len(self.points) < 3:
            raise ValueError(f"Polygon shape {self.id} needs at least 3 points")
        if self.shape_type == ShapeType.KEYPOINTS and not self.keypoints:
            raise ValueError(f"Keypoints shape {self.id} needs at least 1 keypoint")


@dataclass
class ImageAnnotation:
    """All annotations for a single image file."""

    image_path: str
    image_width: int
    image_height: int
    shapes: list[Shape] = field(default_factory=list)

    def add_shape(self, shape: Shape) -> None:
        shape.validate()
        self.shapes.append(shape)

    def remove_shape(self, shape_id: str) -> None:
        self.shapes = [s for s in self.shapes if s.id != shape_id]

    def labels_used(self) -> set[str]:
        return {s.label for s in self.shapes}
