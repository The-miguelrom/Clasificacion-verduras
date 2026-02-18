from app.rules import infer_quality, infer_size
from app.schemas import DefectInput


def test_infer_size_ranges() -> None:
    assert infer_size(120) == "S"
    assert infer_size(180) == "M"
    assert infer_size(250) == "L"


def test_infer_quality_rotten_is_c() -> None:
    defects = [DefectInput(code="podrido_rajadura", score=0.9)]
    quality, confidence, _reason = infer_quality(defects, "M")
    assert quality == "C"
    assert confidence >= 0.9
