"""
Project-level state: the working image directory, class list, and
per-image annotation cache. This is the single source of truth the
GUI reads from and writes to; export/import formats never touch the
GUI directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from annoloom.core.shapes import ImageAnnotation

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

_NUM_RE = re.compile(r"(\d+)")


def _natural_sort_key(path: Path) -> list:
    """Split a filename into text/number chunks so numeric parts sort by
    value, not lexicographically — this makes img2.jpg come before
    img10.jpg instead of after it (plain string sort would put "10"
    before "2" because '1' < '2' as characters)."""
    parts = _NUM_RE.split(path.name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


@dataclass
class Project:
    image_dir: Path
    classes: list[str] = field(default_factory=list)
    annotations: dict[str, ImageAnnotation] = field(default_factory=dict)
    # User-pinned label -> YOLO class ID. When a label has an entry here,
    # exports use this exact number instead of the label's position in
    # `classes`. This lets someone annotating a single-species folder set
    # class ID 2 once and have every box use "2" in the YOLO .txt output,
    # regardless of label list ordering.
    label_class_ids: dict[str, int] = field(default_factory=dict)

    @classmethod
    def open(cls, image_dir: str | Path) -> "Project":
        image_dir = Path(image_dir)
        if not image_dir.is_dir():
            raise NotADirectoryError(f"{image_dir} is not a directory")
        return cls(image_dir=image_dir)

    def list_images(self) -> list[Path]:
        """All images in the folder, natural-sorted so numbered sequences
        (img1, img2, ..., img10, img500 ...) come out in the order a
        person expects rather than plain ASCII string order. This scans
        the whole directory every call so it always reflects the true
        count on disk — no artificial cap, works the same whether the
        folder has 5 images or 50,000."""
        images = [
            p for p in self.image_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        ]
        return sorted(images, key=_natural_sort_key)

    def get_annotation(self, image_path: Path) -> ImageAnnotation | None:
        return self.annotations.get(str(image_path))

    def set_annotation(self, image_path: Path, ann: ImageAnnotation) -> None:
        self.annotations[str(image_path)] = ann

    def ensure_class(self, label: str) -> None:
        if label and label not in self.classes:
            self.classes.append(label)

    def set_class_id(self, label: str, class_id: int) -> None:
        """Pin a label to an explicit numeric class ID for YOLO export."""
        self.ensure_class(label)
        self.label_class_ids[label] = class_id

    def class_id_for(self, label: str) -> int:
        """Resolve the YOLO class ID to use for a label: the user-pinned
        ID if one was set, otherwise the label's position in `classes`
        (the original default behavior)."""
        if label in self.label_class_ids:
            return self.label_class_ids[label]
        if label in self.classes:
            return self.classes.index(label)
        return 0

    def classes_file_path(self) -> Path:
        return self.image_dir / "classes.txt"

    def class_ids_file_path(self) -> Path:
        return self.image_dir / "class_ids.txt"

    def load_classes(self) -> None:
        path = self.classes_file_path()
        if path.exists():
            self.classes = [
                line.strip() for line in path.read_text().splitlines() if line.strip()
            ]
        ids_path = self.class_ids_file_path()
        if ids_path.exists():
            self.label_class_ids = {}
            for line in ids_path.read_text().splitlines():
                line = line.strip()
                if not line or "=" not in line:
                    continue
                label, _, id_str = line.partition("=")
                try:
                    self.label_class_ids[label.strip()] = int(id_str.strip())
                except ValueError:
                    continue

    def save_classes(self) -> None:
        self.classes_file_path().write_text("\n".join(self.classes) + "\n")
        if self.label_class_ids:
            lines = [f"{label}={cid}" for label, cid in self.label_class_ids.items()]
            self.class_ids_file_path().write_text("\n".join(lines) + "\n")
