from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, Float, Integer, String, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_code: Mapped[str] = mapped_column(String(50), index=True)
    supplier_name: Mapped[str] = mapped_column(String(120), index=True)
    product: Mapped[str] = mapped_column(String(50), default="tomate")
    username: Mapped[str] = mapped_column(String(80), index=True)
    quality_class: Mapped[str] = mapped_column(String(1), index=True)
    size_class: Mapped[str] = mapped_column(String(1), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    defects: Mapped[dict[str, Any]] = mapped_column(JSON)
    original_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    annotated_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


engine = create_engine("sqlite:///./mvp.db", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base.metadata.create_all(engine)


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


def infer_size(size_px: int) -> Literal["S", "M", "L"]:
    if size_px < 130:
        return "S"
    if size_px <= 220:
        return "M"
    return "L"


def infer_quality(defects: list[DefectInput], size_class: str) -> tuple[Literal["A", "B", "C"], float, str]:
    if any(d.code == "podrido_rajadura" and d.score >= 0.35 for d in defects):
        return "C", 0.93, "Regla: podredumbre/rajadura detectada"

    medium_defect = any(d.code in {"mancha", "magulladura"} and d.score >= 0.40 for d in defects)
    if medium_defect:
        return "B", 0.82, "Regla: defecto moderado visible"

    if size_class in {"M", "L"} and len(defects) == 0:
        return "A", 0.90, "Regla: sin defectos y tamaño en rango"

    return "B", 0.68, "Regla: condición intermedia"


app = FastAPI(title="MVP Clasificación Tomate", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/inspect", response_model=InspectResponse)
def inspect(payload: InspectRequest) -> InspectResponse:
    size_class = infer_size(payload.manual_size_px)
    quality_class, confidence, _reason = infer_quality(payload.detected_defects, size_class)
    annotated_path = f"annotations/{payload.lot_code}_{datetime.utcnow().timestamp():.0f}.jpg"

    with SessionLocal() as session:
        row = Inspection(
            lot_code=payload.lot_code,
            supplier_name=payload.supplier_name,
            product=payload.product,
            username=payload.username,
            quality_class=quality_class,
            size_class=size_class,
            confidence=confidence,
            defects=[d.model_dump() for d in payload.detected_defects],
            original_image_path=payload.original_image_path,
            annotated_image_path=annotated_path,
        )
        session.add(row)
        session.commit()
        session.refresh(row)

    return InspectResponse(
        inspection_id=row.id,
        quality_class=quality_class,
        size_class=size_class,
        confidence=confidence,
        defects=payload.detected_defects,
        annotated_image_path=annotated_path,
    )


@app.get("/inspections")
def list_inspections(
    lot_code: str | None = None,
    supplier_name: str | None = None,
    quality_class: Literal["A", "B", "C"] | None = None,
) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        query = session.query(Inspection)
        if lot_code:
            query = query.filter(Inspection.lot_code == lot_code)
        if supplier_name:
            query = query.filter(Inspection.supplier_name == supplier_name)
        if quality_class:
            query = query.filter(Inspection.quality_class == quality_class)

        rows = query.order_by(Inspection.created_at.desc()).limit(200).all()
        return [
            {
                "id": r.id,
                "lot_code": r.lot_code,
                "supplier_name": r.supplier_name,
                "product": r.product,
                "quality_class": r.quality_class,
                "size_class": r.size_class,
                "confidence": r.confidence,
                "defects": r.defects,
                "annotated_image_path": r.annotated_image_path,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


@app.get("/reports")
def reports() -> dict[str, Any]:
    with SessionLocal() as session:
        total = session.query(func.count(Inspection.id)).scalar() or 0
        by_quality = {
            quality: count
            for quality, count in session.query(Inspection.quality_class, func.count(Inspection.id))
            .group_by(Inspection.quality_class)
            .all()
        }
        by_supplier = {
            supplier: count
            for supplier, count in session.query(Inspection.supplier_name, func.count(Inspection.id))
            .group_by(Inspection.supplier_name)
            .all()
        }

    rejection_pct = round((by_quality.get("C", 0) / total) * 100, 2) if total else 0.0
    return {
        "total_inspections": total,
        "rejection_pct": rejection_pct,
        "quality_distribution": by_quality,
        "supplier_ranking": by_supplier,
    }
