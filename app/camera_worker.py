import argparse
from datetime import datetime

import cv2
import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Captura desde cámara y envía imagen a /inspect-file")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/inspect-file")
    parser.add_argument("--camera", default="0", help="Índice de cámara USB (0) o URL rtsp/http")
    parser.add_argument("--lot", required=True)
    parser.add_argument("--supplier", required=True)
    parser.add_argument("--username", default="operario1")
    parser.add_argument("--product", default="tomate")
    return parser.parse_args()


def open_camera(camera_arg: str) -> cv2.VideoCapture:
    source = int(camera_arg) if camera_arg.isdigit() else camera_arg
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir la cámara: {camera_arg}")
    return cap


def send_frame(frame, args: argparse.Namespace) -> None:
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        print("No se pudo codificar frame")
        return

    filename = f"{args.lot}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
    files = {"image": (filename, encoded.tobytes(), "image/jpeg")}
    data = {
        "lot_code": args.lot,
        "supplier_name": args.supplier,
        "username": args.username,
        "product": args.product,
    }

    response = requests.post(args.api_url, files=files, data=data, timeout=20)
    if response.ok:
        payload = response.json()
        print(
            f"OK id={payload['inspection_id']} calidad={payload['quality_class']} "
            f"calibre={payload['size_class']} conf={payload['confidence']:.2f}"
        )
    else:
        print(f"Error API {response.status_code}: {response.text}")


def main() -> None:
    args = parse_args()
    cap = open_camera(args.camera)

    print("Presiona [ESPACIO] para capturar y analizar. Presiona [q] para salir.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("No se pudo leer frame")
            break

        preview = frame.copy()
        cv2.putText(
            preview,
            "ESPACIO=inspeccionar | q=salir",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )
        cv2.imshow("Estacion de inspeccion - Tomate", preview)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        if key == 32:
            send_frame(frame, args)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
