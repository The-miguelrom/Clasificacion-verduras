from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from sqlalchemy import JSON, DateTime, Float, Integer, String, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.rules import infer_quality, infer_size
from app.schemas import DefectInput, InspectRequest, InspectResponse
from app.vision import annotate_image, detect_defects_basic, estimate_size_px, load_image_from_bytes, save_upload
from app.web_ui import build_ui_html


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

app = FastAPI(title="MVP Clasificación Tomate", version="0.2.0")
app.mount("/annotations", StaticFiles(directory="annotations"), name="annotations")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


def persist_inspection(
    lot_code: str,
    supplier_name: str,
    product: str,
    username: str,
    quality_class: str,
    size_class: str,
    confidence: float,
    defects: list[DefectInput],
    original_image_path: str | None,
    annotated_image_path: str,
) -> int:
    with SessionLocal() as session:
        row = Inspection(
            lot_code=lot_code,
            supplier_name=supplier_name,
            product=product,
            username=username,
            quality_class=quality_class,
            size_class=size_class,
            confidence=confidence,
            defects=[d.model_dump() for d in defects],
            original_image_path=original_image_path,
            annotated_image_path=annotated_image_path,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def web_app():
    return build_ui_html()


@app.post("/inspect", response_model=InspectResponse)
def inspect(payload: InspectRequest) -> InspectResponse:
    size_class = infer_size(payload.manual_size_px)
    quality_class, confidence, _reason = infer_quality(payload.detected_defects, size_class)
    file_stem = f"{payload.lot_code}_{datetime.utcnow().timestamp():.0f}"
    annotated_path = f"annotations/{file_stem}.jpg"

    inspection_id = persist_inspection(
        lot_code=payload.lot_code,
        supplier_name=payload.supplier_name,
        product=payload.product,
        username=payload.username,
        quality_class=quality_class,
        size_class=size_class,
        confidence=confidence,
        defects=payload.detected_defects,
        original_image_path=payload.original_image_path,
        annotated_image_path=annotated_path,
    )

    return InspectResponse(
        inspection_id=inspection_id,
        quality_class=quality_class,
        size_class=size_class,
        confidence=confidence,
        defects=payload.detected_defects,
        annotated_image_path=annotated_path,
    )


@app.post("/inspect-file", response_model=InspectResponse)
async def inspect_file(
    lot_code: str = Form(...),
    supplier_name: str = Form(...),
    username: str = Form(...),
    product: str = Form("tomate"),
    image: UploadFile = File(...),
) -> InspectResponse:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Archivo inválido: debe ser imagen")

    image_bytes = await image.read()
    file_stem = f"{lot_code}_{datetime.utcnow().timestamp():.0f}"
    original_path = str(save_upload(image_bytes, file_stem))

    try:
        frame = load_image_from_bytes(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    size_px = estimate_size_px(frame)
    defects = detect_defects_basic(frame)
    size_class = infer_size(size_px)
    quality_class, confidence, _reason = infer_quality(defects, size_class)
    annotated_path = annotate_image(frame, quality_class, size_class, defects, file_stem)

    inspection_id = persist_inspection(
        lot_code=lot_code,
        supplier_name=supplier_name,
        product=product,
        username=username,
        quality_class=quality_class,
        size_class=size_class,
        confidence=confidence,
        defects=defects,
        original_image_path=original_path,
        annotated_image_path=annotated_path,
    )

    return InspectResponse(
        inspection_id=inspection_id,
        quality_class=quality_class,
        size_class=size_class,
        confidence=confidence,
        defects=defects,
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
