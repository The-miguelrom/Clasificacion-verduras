from pathlib import Path


def test_web_ui_contains_open_camera_button() -> None:
    content = Path("app/web_ui.py").read_text(encoding="utf-8")
    assert "Abrir cámara" in content
    assert "navigator.mediaDevices.getUserMedia" in content
