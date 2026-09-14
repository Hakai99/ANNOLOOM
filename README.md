<div align="center">

<img src="annoloom/annoloom/resources/logo.png" alt="AnnoLoom logo" width="320"/>

# AnnoLoom

**A modern desktop image annotation tool for computer vision datasets**

Bounding boxes, polygons, and keypoints — in one clean PyQt6 app.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://pypi.org/project/PyQt6/)

</div>

---

## Install

```bash
pip install annoloom
```

## Run

```bash
annoloom
```

Then Open Folder and point it at a directory of images. Draw boxes,
polygons, or keypoint sets, assign labels, and save.

## AnnoLoom UI
<img src="AnnoLoomUI.png" alt="AnnoLoom UI" height= "480" width="854"/>

## AnnoLoom Annotations Marking
<img src="DemoAnnotation.png" alt="AnnoLoom Demo" height= "480" width="854"/>

## Features

- **Three shape types**: bounding boxes, polygons, and labeled keypoints
  (with optional skeleton connections for pose-style annotation).
- **DrawAnnote / DelAnnote workflow**: click DrawAnnote, draw a shape,
  it auto-finishes; select a shape in the list and click DelAnnote to
  remove it.
- **White crosshair guide lines** follow your cursor while drawing,
   to help line up box edges precisely.
- **Auto-fit, centered canvas**: images scale to fill the available
  space and stay centered — no more tiny thumbnails in the corner.
- **Natural, numeric image ordering**: files like `img2.jpg`, `img10.jpg`,
  `img100.jpg` are listed in true numeric order, not ASCII string order
  (which would otherwise put `img10` before `img2`). Folder scans are
  fully dynamic — 5 images or 50,000, all of them show up.
- **`[current / total]` counter** in the title bar, e.g. `[3 / 500]`,
  updating only when you actually switch images.
- **Custom YOLO class numbers**: type any number into "YOLO class number
  for this label" and every box with that label is saved with exactly
  that number in YOLO `.txt` exports — independent of label list order —
  until you change it. Useful when annotating one species/class per
  folder and you want a fixed ID like `2` throughout.
- **Big, unmissable "✓ Labels saved successfully" banner** on every
  save/export, instead of only a small status-bar message.
- **Native save format** (`<image>.aloom.json`): lossless, keeps every
  field for every shape type — this is what autosave/`Ctrl+S` writes.
- **Export formats**:
  - YOLO (`.txt`, normalized box coordinates, custom class numbers)
  - Pascal VOC (`.xml`)
  - COCO (`.json`, supports boxes, polygon segmentations, and keypoints)

  YOLO and Pascal VOC only support bounding boxes in their original
  specs, so polygon/keypoint shapes are skipped on export to those
  formats with an on-screen warning listing exactly what was skipped —
  nothing is silently dropped. Use COCO export if you need full fidelity
  for polygons or keypoints in an interchange format.
- **Dark, modern UI** with your own logo as the app icon, an image list,
  live shape list per image, and inline label editing.

## Data model

Internally every shape is stored in a small dataclass model
(`annoloom.core.shapes`) at full float precision in image-pixel space.
Conversion to integers happens only at the point of use — drawing or a
format that requires them — using rounding, not truncation.

## Development

```bash
git clone <this repo>
cd annoloom
pip install -e .
python -m annoloom.app
```

## Building a standalone .exe (Windows)

No Python install needed for the person running the app — just build
once and share the resulting `.exe`.

1. Make sure you have Python 3.9+ and this project installed
   (`pip install -e .`), then from inside the `annoloom` folder run:

   ```
   build_exe.bat
   ```

2. This installs PyInstaller if needed and builds using `AnnoLoom.spec`.
3. When it finishes, your executable is at `dist\AnnoLoom.exe`. Copy
   that single file anywhere — it runs standalone, no terminal, no
   `pip install` required on the target machine.

> **Note:** PyInstaller builds are platform-specific — build on Windows
> to get a Windows `.exe`; the same steps on macOS/Linux would produce
> a Mac/Linux binary instead.

## License

MIT
