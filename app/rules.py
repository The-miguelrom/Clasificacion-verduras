from typing import Literal

from app.schemas import DefectInput


QualityClass = Literal["A", "B", "C"]
SizeClass = Literal["S", "M", "L"]


def infer_size(size_px: int) -> SizeClass:
    if size_px < 130:
        return "S"
    if size_px <= 220:
        return "M"
    return "L"


def infer_quality(defects: list[DefectInput], size_class: str) -> tuple[QualityClass, float, str]:
    if any(d.code == "podrido_rajadura" and d.score >= 0.35 for d in defects):
        return "C", 0.93, "Regla: podredumbre/rajadura detectada"

    medium_defect = any(d.code in {"mancha", "magulladura"} and d.score >= 0.40 for d in defects)
    if medium_defect:
        return "B", 0.82, "Regla: defecto moderado visible"

    if size_class in {"M", "L"} and len(defects) == 0:
        return "A", 0.90, "Regla: sin defectos y tamaño en rango"

    return "B", 0.68, "Regla: condición intermedia"
