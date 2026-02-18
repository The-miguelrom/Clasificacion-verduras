from typing import Literal

from pydantic import BaseModel, Field


class DefectInput(BaseModel):
    code: Literal["mancha", "magulladura", "podrido_rajadura"]
    score: float = Field(ge=0, le=1)


class InspectRequest(BaseModel):
    lot_code: str
    supplier_name: str
    product: str = "tomate"
    username: str
    manual_size_px: int = Field(default=180, ge=1)
    detected_defects: list[DefectInput] = Field(default_factory=list)
    original_image_path: str | None = None


class InspectResponse(BaseModel):
    inspection_id: int
    quality_class: Literal["A", "B", "C"]
    size_class: Literal["S", "M", "L"]
    confidence: float
    defects: list[DefectInput]
    annotated_image_path: str
