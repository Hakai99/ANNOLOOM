"""
AnnoLoom main window: toolbar for tool/format selection, image list
sidebar, the canvas in the center, and a labels panel.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QPixmap, QKeySequence, QIcon, QIntValidator
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QToolBar, QFileDialog, QLabel, QLineEdit,
    QPushButton, QMessageBox, QScrollArea, QComboBox, QStatusBar,
)

LOGO_PATH = Path(__file__).resolve().parent.parent / "resources" / "logo.png"

from annoloom.core.project import Project
from annoloom.core.shapes import ImageAnnotation, ShapeType
from annoloom.formats.native import load_native, save_native
from annoloom.formats.yolo import export_yolo
from annoloom.formats.pascal_voc import export_pascal_voc
from annoloom.formats.coco import export_coco
from annoloom.ui.canvas import Canvas

DARK_STYLESHEET = """
QMainWindow, QWidget { background-color: #1e1f26; color: #e8e8ec; font-family: 'Segoe UI', sans-serif; }
QToolBar { background-color: #262832; border: none; spacing: 6px; padding: 6px; }
QListWidget { background-color: #262832; border: 1px solid #343640; border-radius: 6px; }
QListWidget::item:selected { background-color: #4f7cff; border-radius: 4px; }
QPushButton { background-color: #34364a; border: 1px solid #454864; border-radius: 6px; padding: 6px 12px; }
QPushButton:hover { background-color: #454864; }
QPushButton:pressed { background-color: #4f7cff; }
QPushButton#drawBtn { background-color: #1f7a4d; border: 1px solid #2ea86b; font-weight: 600; }
QPushButton#drawBtn:hover { background-color: #2ea86b; }
QPushButton#drawBtn:checked { background-color: #2ea86b; border: 1px solid #6bffc0; }
QPushButton#delBtn { background-color: #7a2530; border: 1px solid #a83b4a; font-weight: 600; }
QPushButton#delBtn:hover { background-color: #a83b4a; }
QLineEdit, QComboBox { background-color: #262832; border: 1px solid #34364a; border-radius: 6px; padding: 4px 8px; }
QStatusBar { background-color: #262832; }
QLabel#sectionTitle { color: #9aa0c0; font-weight: 600; padding: 4px 0; }
QScrollArea { background-color: #14151a; border: none; }
QScrollArea > QWidget > QWidget { background-color: #14151a; }
QLabel#saveBanner {
    background-color: #1f7a4d;
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    border: 2px solid #6bffc0;
    border-radius: 10px;
    padding: 14px 28px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnnoLoom — image annotation")
        self.resize(1280, 800)
        self.setStyleSheet(DARK_STYLESHEET)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        self.project: Project | None = None
        self.current_image_path: Path | None = None
        self.current_annotation: ImageAnnotation | None = None
        self.labels_output_dir: Path | None = None
        self.current_image_index: int = -1  # 0-based index into project.list_images()

        self._build_ui()
        self._build_toolbar()
        self._build_save_banner()

    # ---- UI construction -----------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)

        # Left: image list
        left_panel = QVBoxLayout()
        left_title = QLabel("Images")
        left_title.setObjectName("sectionTitle")
        left_panel.addWidget(left_title)
        self.image_list = QListWidget()
        self.image_list.currentItemChanged.connect(self._on_image_selected)
        left_panel.addWidget(self.image_list)
        left_container = QWidget()
        left_container.setLayout(left_panel)
        left_container.setFixedWidth(220)

        # Center: canvas, centered inside a scroll area that fills all
        # available space so the image is never squeezed into a corner.
        self.canvas = Canvas()
        self.canvas.shapeCreated.connect(self._on_shape_created)
        self.canvas.shapeFinished.connect(self._on_shape_tool_finished)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Right: labels + class input
        right_panel = QVBoxLayout()

        right_title = QLabel("Current label")
        right_title.setObjectName("sectionTitle")
        right_panel.addWidget(right_title)
        self.label_input = QLineEdit("object")
        self.label_input.textChanged.connect(self._on_label_changed)
        right_panel.addWidget(self.label_input)

        class_id_title = QLabel("YOLO class number for this label")
        class_id_title.setObjectName("sectionTitle")
        right_panel.addWidget(class_id_title)
        self.class_id_input = QLineEdit("0")
        self.class_id_input.setValidator(QIntValidator(0, 999999))
        self.class_id_input.setToolTip(
            "Set the exact number that will appear in YOLO .txt files for "
            "the current label above. E.g. set this to 2 and every box "
            "labeled 'Buffalo' will be saved as class 2, until you change it."
        )
        self.class_id_input.editingFinished.connect(self._on_class_id_changed)
        right_panel.addWidget(self.class_id_input)

        tool_title = QLabel("Shape type")
        tool_title.setObjectName("sectionTitle")
        right_panel.addWidget(tool_title)
        self.tool_combo = QComboBox()
        self.tool_combo.addItems(["Box", "Polygon", "Keypoints"])
        self.tool_combo.currentTextChanged.connect(self._on_tool_changed)
        right_panel.addWidget(self.tool_combo)

        action_title = QLabel("Annotate")
        action_title.setObjectName("sectionTitle")
        right_panel.addWidget(action_title)

        self.draw_btn = QPushButton("DrawAnnote")
        self.draw_btn.setObjectName("drawBtn")
        self.draw_btn.setCheckable(True)
        self.draw_btn.setToolTip(
            "Click, then draw on the image.\n"
            "Box: click-drag two corners.\n"
            "Polygon: click each point, double-click or right-click to finish.\n"
            "Keypoints: click each point, double-click to finish."
        )
        self.draw_btn.clicked.connect(self._on_draw_toggled)
        right_panel.addWidget(self.draw_btn)

        self.del_btn = QPushButton("DelAnnote")
        self.del_btn.setObjectName("delBtn")
        self.del_btn.setToolTip("Select a shape below, then click this to delete it.")
        self.del_btn.clicked.connect(self._delete_selected_shape)
        right_panel.addWidget(self.del_btn)

        shapes_title = QLabel("Shapes on this image")
        shapes_title.setObjectName("sectionTitle")
        right_panel.addWidget(shapes_title)
        self.shape_list = QListWidget()
        self.shape_list.currentItemChanged.connect(self._on_shape_list_selection)
        right_panel.addWidget(self.shape_list, stretch=1)

        right_container = QWidget()
        right_container.setLayout(right_panel)
        right_container.setFixedWidth(240)

        layout.addWidget(left_container)
        layout.addWidget(self.scroll, stretch=1)
        layout.addWidget(right_container)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open Image Folder", self)
        open_action.triggered.connect(self._open_folder)
        toolbar.addAction(open_action)

        labels_folder_action = QAction("Set Labels Folder", self)
        labels_folder_action.setToolTip("Choose where exported/saved label files are written")
        labels_folder_action.triggered.connect(self._choose_labels_folder)
        toolbar.addAction(labels_folder_action)

        toolbar.addSeparator()

        save_action = QAction("Save (native)", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._save_current)
        toolbar.addAction(save_action)

        export_yolo_action = QAction("Export YOLO", self)
        export_yolo_action.triggered.connect(self._export_yolo)
        toolbar.addAction(export_yolo_action)

        export_voc_action = QAction("Export Pascal VOC", self)
        export_voc_action.triggered.connect(self._export_voc)
        toolbar.addAction(export_voc_action)

        export_coco_action = QAction("Export COCO", self)
        export_coco_action.triggered.connect(self._export_coco)
        toolbar.addAction(export_coco_action)

    def _build_save_banner(self) -> None:
        """A large, hard-to-miss overlay banner for save confirmations —
        the status bar text alone is too easy to miss at the bottom edge."""
        self.save_banner = QLabel("", self)
        self.save_banner.setObjectName("saveBanner")
        self.save_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.save_banner.hide()
        self._banner_timer = QTimer(self)
        self._banner_timer.setSingleShot(True)
        self._banner_timer.timeout.connect(self.save_banner.hide)

    def _show_save_banner(self, text: str, duration_ms: int = 1800) -> None:
        self.save_banner.setText(text)
        self.save_banner.adjustSize()
        # Center horizontally over the canvas area, near the top so it
        # doesn't block the image the user is working on.
        x = (self.width() - self.save_banner.width()) // 2
        y = 90
        self.save_banner.move(x, y)
        self.save_banner.show()
        self.save_banner.raise_()
        self._banner_timer.start(duration_ms)

    def resizeEvent(self, event) -> None:
        if self.save_banner.isVisible():
            x = (self.width() - self.save_banner.width()) // 2
            self.save_banner.move(x, 90)
        super().resizeEvent(event)

    # ---- project / image handling ----------------------------------------

    def _open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open image folder")
        if not folder:
            return
        self.project = Project.open(folder)
        self.project.load_classes()
        self.image_list.clear()
        images = self.project.list_images()
        for img_path in images:
            item = QListWidgetItem(img_path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(img_path))
            self.image_list.addItem(item)
        self.current_image_index = -1
        self._update_title()
        self.statusBar().showMessage(f"Loaded {len(images)} images from {folder}")

    def _choose_labels_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose folder to save label files")
        if not folder:
            return
        self.labels_output_dir = Path(folder)
        self.statusBar().showMessage(f"Label files will be saved to: {folder}")

    def _label_output_path(self, filename: str) -> Path:
        """Resolve where a label file should be written: the user-chosen
        labels folder if set, otherwise next to the image (old behavior)."""
        if self.labels_output_dir is not None:
            return self.labels_output_dir / filename
        return self.current_image_path.parent / filename

    def _update_title(self) -> None:
        """Show [current/total] in the window title, e.g. [1 / 500].
        This only changes when the selected image actually changes (see
        _on_image_selected), never on every save or shape edit, so the
        count stays a clean image-position indicator."""
        total = self.image_list.count()
        if total == 0 or self.current_image_index < 0:
            self.setWindowTitle("AnnoLoom — image annotation")
            return
        position = self.current_image_index + 1  # 1-based for display
        name = self.current_image_path.name if self.current_image_path else ""
        self.setWindowTitle(f"AnnoLoom — {name} [{position} / {total}]")

    def _on_image_selected(self, current: QListWidgetItem, _previous) -> None:
        if current is None or self.project is None:
            return
        img_path = Path(current.data(Qt.ItemDataRole.UserRole))
        self.current_image_index = self.image_list.row(current)
        self._load_image(img_path)
        self._update_title()

    def _load_image(self, img_path: Path) -> None:
        pixmap = QPixmap(str(img_path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Error", f"Could not load image: {img_path}")
            return

        self.current_image_path = img_path
        self.canvas.load_pixmap(pixmap)

        sidecar = self._label_output_path(img_path.stem + ".aloom.json")
        if sidecar.exists():
            ann = load_native(sidecar)
        else:
            ann = ImageAnnotation(
                image_path=str(img_path),
                image_width=pixmap.width(),
                image_height=pixmap.height(),
            )
        self.current_annotation = ann
        self.canvas.shapes = list(ann.shapes)
        self.canvas.update()
        self._refresh_shape_list()

    def _refresh_shape_list(self) -> None:
        self.shape_list.clear()
        if not self.current_annotation:
            return
        for shape in self.current_annotation.shapes:
            item = QListWidgetItem(f"{shape.shape_type.value}: {shape.label}")
            item.setData(Qt.ItemDataRole.UserRole, shape.id)
            self.shape_list.addItem(item)

    # ---- tool / label changes --------------------------------------------

    def _on_tool_changed(self, text: str) -> None:
        mapping = {"Box": ShapeType.BOX, "Polygon": ShapeType.POLYGON, "Keypoints": ShapeType.KEYPOINTS}
        self.canvas.active_tool = mapping[text]

    def _on_label_changed(self, text: str) -> None:
        self.canvas.current_label = text or "object"
        # Reflect this label's pinned class ID (if any) in the class ID
        # box, so switching labels shows the right number rather than
        # leaving a stale value from the previous label.
        if self.project:
            class_id = self.project.label_class_ids.get(self.canvas.current_label)
            if class_id is not None:
                self.class_id_input.blockSignals(True)
                self.class_id_input.setText(str(class_id))
                self.class_id_input.blockSignals(False)

    def _on_class_id_changed(self) -> None:
        """Pin the current label to the number typed in the class-ID box.
        This number is then used verbatim in every YOLO export for this
        label until changed again — it does not shift if new labels are
        added or removed."""
        text = self.class_id_input.text().strip()
        if not text:
            return
        class_id = int(text)
        label = self.canvas.current_label
        if self.project is None:
            # No folder open yet — nothing to pin against, but keep the
            # value so it applies as soon as a folder/project exists.
            return
        self.project.set_class_id(label, class_id)
        self.project.save_classes()
        self.statusBar().showMessage(f"Label '{label}' will be saved as YOLO class {class_id}")

    def _on_draw_toggled(self, checked: bool) -> None:
        """DrawAnnote is a toggle: on = canvas accepts clicks to build a
        new shape; off = clicks just select/inspect existing shapes."""
        self.canvas.drawing_enabled = checked
        if checked:
            self.statusBar().showMessage("Drawing mode on — click on the image to annotate.")
        else:
            self.statusBar().showMessage("Drawing mode off.")

    def _on_shape_created(self, shape) -> None:
        if self.current_annotation is None:
            return
        self.current_annotation.shapes.append(shape)
        if self.project:
            self.project.ensure_class(shape.label)
        self._refresh_shape_list()

    def _on_shape_tool_finished(self) -> None:
        """Called by the canvas after a shape is completed — automatically
        un-toggles DrawAnnote so the user doesn't immediately start a second
        shape by accident, matching labelImg's one-shape-per-click habit."""
        self.draw_btn.setChecked(False)
        self.canvas.drawing_enabled = False

    def _on_shape_list_selection(self, current: QListWidgetItem, _previous) -> None:
        if current is None:
            self.canvas.selected_shape_id = None
        else:
            self.canvas.selected_shape_id = current.data(Qt.ItemDataRole.UserRole)
        self.canvas.update()

    def _delete_selected_shape(self) -> None:
        item = self.shape_list.currentItem()
        if item is None or self.current_annotation is None:
            QMessageBox.information(self, "No shape selected", "Select a shape in the list first, then click DelAnnote.")
            return
        shape_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_annotation.remove_shape(shape_id)
        self.canvas.shapes = list(self.current_annotation.shapes)
        self.canvas.selected_shape_id = None
        self.canvas.update()
        self._refresh_shape_list()

    # ---- save / export -----------------------------------------------------

    def _save_current(self) -> None:
        if not self.current_annotation or not self.current_image_path:
            return
        sidecar = self._label_output_path(self.current_image_path.stem + ".aloom.json")
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        save_native(self.current_annotation, sidecar)
        if self.project:
            self.project.save_classes()
        self.statusBar().showMessage(f"Saved {sidecar}")
        self._show_save_banner("✓ Labels saved successfully")

    def _export_yolo(self) -> None:
        if not self.current_annotation or not self.project:
            return
        out_path = self._label_output_path(self.current_image_path.stem + ".txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        warnings = export_yolo(
            self.current_annotation,
            self.project.classes,
            out_path,
            class_id_resolver=self.project.class_id_for,
        )
        self._report_warnings(warnings, f"Exported YOLO to {out_path}")
        if not warnings:
            self._show_save_banner("✓ Labels saved successfully")

    def _export_voc(self) -> None:
        if not self.current_annotation:
            return
        out_path = self._label_output_path(self.current_image_path.stem + ".xml")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        warnings = export_pascal_voc(self.current_annotation, out_path)
        self._report_warnings(warnings, f"Exported Pascal VOC to {out_path}")
        if not warnings:
            self._show_save_banner("✓ Labels saved successfully")

    def _export_coco(self) -> None:
        if not self.project:
            return
        default_dir = str(self.labels_output_dir) if self.labels_output_dir else ""
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Export COCO JSON", directory=default_dir, filter="JSON (*.json)"
        )
        if not out_path:
            return
        all_annotations = []
        for img_path in self.project.list_images():
            sidecar = self._label_output_path(img_path.stem + ".aloom.json")
            if sidecar.exists():
                all_annotations.append(load_native(sidecar))
        export_coco(all_annotations, self.project.classes, out_path)
        self.statusBar().showMessage(f"Exported COCO to {out_path}")
        self._show_save_banner("✓ Labels saved successfully")

    def _report_warnings(self, warnings: list[str], success_message: str) -> None:
        if warnings:
            QMessageBox.warning(self, "Export completed with warnings", "\n".join(warnings))
        self.statusBar().showMessage(success_message)
