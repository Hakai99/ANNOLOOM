"""
The interactive image canvas: displays the current image and lets the
user draw/edit boxes, polygons, and keypoints on top of it.

Design note on the float/int bug class that plagues older forks of this
kind of tool: PyQt6's QPainter drawing calls (drawLine, drawRect,
drawEllipse, etc.) require integer arguments in most overloads. Mouse
events, however, report float positions (QPointF). Every single place
in this file that turns a stored/mouse coordinate into a drawing call
goes through `_qpoint(...)` or `Point.as_int_tuple()`, which round
(not truncate) to the nearest pixel. There is intentionally no bare
`.x()` / `.y()` passed directly into a paint call anywhere below.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QPolygonF, QMouseEvent, QPaintEvent
from PyQt6.QtWidgets import QWidget

from annoloom.core.shapes import Point, Shape, ShapeType, Keypoint

BOX_COLOR = QColor(0, 200, 120)
POLYGON_COLOR = QColor(80, 160, 255)
KEYPOINT_COLOR = QColor(255, 170, 30)
SELECTED_COLOR = QColor(255, 60, 90)
VERTEX_RADIUS = 4


def _qpoint(p: Point) -> QPointF:
    """Convert a stored Point to a QPointF for geometry ops."""
    return QPointF(p.x, p.y)


def _int_pair(p: Point) -> tuple[int, int]:
    """Round (never truncate) to ints for pixel-exact drawing calls."""
    return p.as_int_tuple()


class Canvas(QWidget):
    shapeCreated = pyqtSignal(Shape)
    shapeSelected = pyqtSignal(str)  # shape id
    shapeFinished = pyqtSignal()  # emitted once a shape is fully completed

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 200)

        self.pixmap: QPixmap | None = None
        self.scale: float = 1.0
        self.auto_fit: bool = True

        self.shapes: list[Shape] = []
        self.selected_shape_id: str | None = None

        self.active_tool: ShapeType = ShapeType.BOX
        self.current_label: str = "object"

        # Gate: only accept new-shape clicks while the DrawAnnote button is
        # toggled on. When off, clicks are reserved for future select/move
        # interactions rather than accidentally starting a new shape.
        self.drawing_enabled: bool = False

        # In-progress drawing state
        self._drawing_points: list[Point] = []
        self._cursor_pos: Point | None = None
        self._dragging_vertex: tuple[str, int] | None = None  # (shape_id, vertex_index)

    # ---- image loading -------------------------------------------------

    def load_pixmap(self, pixmap: QPixmap) -> None:
        self.pixmap = pixmap
        self.auto_fit = True
        self._recompute_fit_scale()
        self.update()

    def set_scale(self, scale: float) -> None:
        self.auto_fit = False
        self.scale = max(0.05, scale)
        self._resize_to_content()
        self.update()

    def _recompute_fit_scale(self) -> None:
        """Scale the image to fill the available viewport (parent scroll
        area's viewport) while preserving aspect ratio, rather than always
        showing images at native pixel size."""
        if self.pixmap is None:
            return
        viewport = self.parent()
        avail_w = viewport.width() if viewport is not None else self.pixmap.width()
        avail_h = viewport.height() if viewport is not None else self.pixmap.height()
        avail_w = max(avail_w, 100)
        avail_h = max(avail_h, 100)

        scale_w = avail_w / self.pixmap.width()
        scale_h = avail_h / self.pixmap.height()
        self.scale = max(min(scale_w, scale_h), 0.05)
        self._resize_to_content()

    def _resize_to_content(self) -> None:
        if self.pixmap is None:
            return
        self.setFixedSize(
            round(self.pixmap.width() * self.scale),
            round(self.pixmap.height() * self.scale),
        )

    def resizeEvent(self, event) -> None:
        # Re-fit whenever the surrounding viewport changes size, unless the
        # user has manually zoomed (auto_fit is turned off by set_scale).
        if self.auto_fit and self.pixmap is not None:
            self._recompute_fit_scale()
        super().resizeEvent(event)

    # ---- coordinate mapping ---------------------------------------------

    def widget_to_image(self, pos: QPointF) -> Point:
        """Map a widget-space mouse position to image-pixel space."""
        return Point(pos.x() / self.scale, pos.y() / self.scale)

    # ---- mouse handling --------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.pixmap is None or not self.drawing_enabled:
            return
        img_pt = self.widget_to_image(event.position())

        if event.button() == Qt.MouseButton.LeftButton:
            if self.active_tool == ShapeType.BOX:
                self._drawing_points.append(img_pt)
                if len(self._drawing_points) == 2:
                    self._finish_box()
            elif self.active_tool == ShapeType.POLYGON:
                self._drawing_points.append(img_pt)
            elif self.active_tool == ShapeType.KEYPOINTS:
                self._add_keypoint(img_pt)

        elif event.button() == Qt.MouseButton.RightButton:
            if self.active_tool == ShapeType.POLYGON and len(self._drawing_points) >= 3:
                self._finish_polygon()

        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._cursor_pos = self.widget_to_image(event.position())
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if not self.drawing_enabled:
            return
        if self.active_tool == ShapeType.POLYGON and len(self._drawing_points) >= 3:
            self._finish_polygon()
        elif self.active_tool == ShapeType.KEYPOINTS and self._drawing_points:
            self._finish_keypoints()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._drawing_points.clear()
            self.update()
        super().keyPressEvent(event)

    # ---- shape completion --------------------------------------------------

    def _finish_box(self) -> None:
        p1, p2 = self._drawing_points
        x_min, x_max = sorted([p1.x, p2.x])
        y_min, y_max = sorted([p1.y, p2.y])
        shape = Shape(
            shape_type=ShapeType.BOX,
            label=self.current_label,
            points=[Point(x_min, y_min), Point(x_max, y_max)],
        )
        self.shapes.append(shape)
        self.shapeCreated.emit(shape)
        self._drawing_points.clear()
        self.shapeFinished.emit()

    def _finish_polygon(self) -> None:
        shape = Shape(
            shape_type=ShapeType.POLYGON,
            label=self.current_label,
            points=list(self._drawing_points),
        )
        self.shapes.append(shape)
        self.shapeCreated.emit(shape)
        self._drawing_points.clear()
        self.shapeFinished.emit()

    def _add_keypoint(self, pt: Point) -> None:
        self._drawing_points.append(pt)

    def _finish_keypoints(self) -> None:
        keypoints = [
            Keypoint(point=p, label=f"kp{i}", visible=True)
            for i, p in enumerate(self._drawing_points)
        ]
        shape = Shape(shape_type=ShapeType.KEYPOINTS, label=self.current_label, keypoints=keypoints)
        self.shapes.append(shape)
        self.shapeCreated.emit(shape)
        self._drawing_points.clear()
        self.shapeFinished.emit()

    # ---- painting --------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.pixmap is not None:
            scaled = self.pixmap.scaled(
                round(self.pixmap.width() * self.scale),
                round(self.pixmap.height() * self.scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(0, 0, scaled)

        for shape in self.shapes:
            self._paint_shape(painter, shape, selected=(shape.id == self.selected_shape_id))

        self._paint_in_progress(painter)
        self._paint_crosshair(painter)
        painter.end()

    def _pen_for(self, base_color: QColor, selected: bool) -> QPen:
        color = SELECTED_COLOR if selected else base_color
        pen = QPen(color)
        pen.setWidth(2)
        return pen

    def _scaled_int(self, value: float) -> int:
        """Scale an image-space coordinate to widget space and round to int
        for drawing — the single place scaling + int-rounding happens."""
        return round(value * self.scale)

    def _paint_crosshair(self, painter: QPainter) -> None:
        """Full-width/height white guide lines through the cursor, like
        labelImg's targeting cross, shown only while drawing is enabled
        and the cursor is over the image — helps line up box edges."""
        if not self.drawing_enabled or self._cursor_pos is None or self.pixmap is None:
            return

        pen = QPen(QColor(255, 255, 255, 180))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        cx = self._scaled_int(self._cursor_pos.x)
        cy = self._scaled_int(self._cursor_pos.y)
        w = self.width()
        h = self.height()

        painter.drawLine(cx, 0, cx, h)
        painter.drawLine(0, cy, w, cy)

    def _paint_shape(self, painter: QPainter, shape: Shape, selected: bool) -> None:
        if shape.shape_type == ShapeType.BOX:
            self._paint_box(painter, shape, selected)
        elif shape.shape_type == ShapeType.POLYGON:
            self._paint_polygon(painter, shape, selected)
        elif shape.shape_type == ShapeType.KEYPOINTS:
            self._paint_keypoints(painter, shape, selected)

    def _paint_box(self, painter: QPainter, shape: Shape, selected: bool) -> None:
        painter.setPen(self._pen_for(BOX_COLOR, selected))
        p1, p2 = shape.points
        x1, y1 = self._scaled_int(p1.x), self._scaled_int(p1.y)
        x2, y2 = self._scaled_int(p2.x), self._scaled_int(p2.y)
        # QRect wants int x, y, width, height — all rounded above.
        painter.drawRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        painter.drawText(min(x1, x2), max(min(y1, y2) - 4, 10), shape.label)

    def _paint_polygon(self, painter: QPainter, shape: Shape, selected: bool) -> None:
        painter.setPen(self._pen_for(POLYGON_COLOR, selected))
        polygon = QPolygonF([
            QPointF(self._scaled_int(p.x), self._scaled_int(p.y)) for p in shape.points
        ])
        painter.drawPolygon(polygon)
        if shape.points:
            first = shape.points[0]
            painter.drawText(self._scaled_int(first.x), max(self._scaled_int(first.y) - 4, 10), shape.label)

    def _paint_keypoints(self, painter: QPainter, shape: Shape, selected: bool) -> None:
        pen = self._pen_for(KEYPOINT_COLOR, selected)
        painter.setPen(pen)

        # Skeleton connective lines, drawn first so dots sit on top.
        for a_idx, b_idx in shape.skeleton:
            if a_idx < len(shape.keypoints) and b_idx < len(shape.keypoints):
                pa = shape.keypoints[a_idx].point
                pb = shape.keypoints[b_idx].point
                painter.drawLine(
                    self._scaled_int(pa.x), self._scaled_int(pa.y),
                    self._scaled_int(pb.x), self._scaled_int(pb.y),
                )

        for kp in shape.keypoints:
            if not kp.visible:
                continue
            cx, cy = self._scaled_int(kp.point.x), self._scaled_int(kp.point.y)
            painter.drawEllipse(cx - VERTEX_RADIUS, cy - VERTEX_RADIUS, VERTEX_RADIUS * 2, VERTEX_RADIUS * 2)

    def _paint_in_progress(self, painter: QPainter) -> None:
        if not self._drawing_points:
            return

        pen = QPen(QColor(255, 255, 255))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(1)
        painter.setPen(pen)

        pts = [QPointF(self._scaled_int(p.x), self._scaled_int(p.y)) for p in self._drawing_points]

        if self.active_tool == ShapeType.BOX and len(self._drawing_points) == 1 and self._cursor_pos:
            x1, y1 = self._scaled_int(self._drawing_points[0].x), self._scaled_int(self._drawing_points[0].y)
            x2, y2 = self._scaled_int(self._cursor_pos.x), self._scaled_int(self._cursor_pos.y)
            painter.drawRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        elif self.active_tool == ShapeType.POLYGON:
            for i in range(len(pts) - 1):
                painter.drawLine(round(pts[i].x()), round(pts[i].y()), round(pts[i + 1].x()), round(pts[i + 1].y()))
            if self._cursor_pos and pts:
                cx, cy = self._scaled_int(self._cursor_pos.x), self._scaled_int(self._cursor_pos.y)
                painter.drawLine(round(pts[-1].x()), round(pts[-1].y()), cx, cy)
        elif self.active_tool == ShapeType.KEYPOINTS:
            for pt in pts:
                cx, cy = round(pt.x()), round(pt.y())
                painter.drawEllipse(cx - VERTEX_RADIUS, cy - VERTEX_RADIUS, VERTEX_RADIUS * 2, VERTEX_RADIUS * 2)
