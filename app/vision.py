from pathlib import Path

import cv2
import numpy as np

from app.schemas import DefectInput


ANNOTATIONS_DIR = Path("annotations")
UPLOADS_DIR = Path("uploads")
ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(image_bytes: bytes, filename_stem: str) -> Path:
    path = UPLOADS_DIR / f"{filename_stem}.jpg"
    path.write_bytes(image_bytes)
    return path


def estimate_size_px(image: np.ndarray) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 180
    contour = max(contours, key=cv2.contourArea)
    (_, _), radius = cv2.minEnclosingCircle(contour)
    return int(radius * 2)


def detect_defects_basic(image: np.ndarray) -> list[DefectInput]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    defects: list[DefectInput] = []

    dark_mask = cv2.inRange(hsv, (0, 0, 0), (180, 255, 60))
    dark_ratio = float(np.count_nonzero(dark_mask)) / dark_mask.size
    if dark_ratio > 0.015:
        defects.append(DefectInput(code="mancha", score=min(0.95, dark_ratio * 8)))

    brown_mask = cv2.inRange(hsv, (5, 80, 40), (25, 255, 180))
    brown_ratio = float(np.count_nonzero(brown_mask)) / brown_mask.size
    if brown_ratio > 0.01:
        defects.append(DefectInput(code="magulladura", score=min(0.9, brown_ratio * 10)))

    return defects


def annotate_image(image: np.ndarray, quality_class: str, size_class: str, defects: list[DefectInput], filename_stem: str) -> str:
    annotated = image.copy()
    cv2.putText(
        annotated,
        f"Calidad: {quality_class} | Calibre: {size_class}",
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0) if quality_class == "A" else (0, 255, 255) if quality_class == "B" else (0, 0, 255),
        2,
    )
    for idx, defect in enumerate(defects, start=1):
        cv2.putText(
            annotated,
            f"{idx}. {defect.code} ({defect.score:.2f})",
            (20, 30 + idx * 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

    out_path = ANNOTATIONS_DIR / f"{filename_stem}.jpg"
    cv2.imwrite(str(out_path), annotated)
    return str(out_path)


def load_image_from_bytes(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("No se pudo decodificar la imagen")
    return image
