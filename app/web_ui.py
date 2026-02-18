from fastapi.responses import HTMLResponse


def build_ui_html() -> HTMLResponse:
    html = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Inspección Tomate - Cámara</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0f172a; color:#e2e8f0; margin:0; }
    .wrap { max-width: 980px; margin: 0 auto; padding: 24px; }
    h1 { margin-bottom: 8px; }
    .card { background:#1e293b; border-radius:12px; padding:16px; margin-bottom:16px; }
    label { display:block; margin-top:8px; font-size:14px; }
    input { width:100%; padding:10px; margin-top:4px; border-radius:8px; border:1px solid #334155; background:#0b1220; color:#fff; }
    button { padding:10px 14px; border-radius:10px; border:none; cursor:pointer; margin-right:8px; margin-top:12px; }
    .btn-primary { background:#22c55e; color:#082f12; font-weight:600; }
    .btn-secondary { background:#38bdf8; color:#042f49; font-weight:600; }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    video, canvas, img { width:100%; border-radius:12px; background:#000; }
    pre { white-space:pre-wrap; background:#0b1220; padding:12px; border-radius:8px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>MVP Clasificación de Tomate</h1>
    <p>Abre la cámara, captura y envía al backend para obtener calidad A/B/C.</p>

    <div class="card row">
      <div>
        <label>Lote</label><input id="lot" value="L-001" />
        <label>Proveedor</label><input id="supplier" value="Finca Norte" />
        <label>Usuario</label><input id="username" value="operario1" />
        <label>Producto</label><input id="product" value="tomate" />
        <div>
          <button id="openCam" class="btn-secondary">Abrir cámara</button>
          <button id="capture" class="btn-primary">Capturar e inspeccionar</button>
        </div>
      </div>
      <div>
        <video id="video" autoplay playsinline></video>
      </div>
    </div>

    <div class="card row">
      <div>
        <h3>Última captura</h3>
        <canvas id="canvas"></canvas>
      </div>
      <div>
        <h3>Imagen anotada</h3>
        <img id="annotated" alt="imagen anotada" />
      </div>
    </div>

    <div class="card">
      <h3>Resultado</h3>
      <pre id="result">Sin inspecciones aún.</pre>
    </div>
  </div>

  <script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const resultBox = document.getElementById('result');
    const annotatedImg = document.getElementById('annotated');

    document.getElementById('openCam').addEventListener('click', async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        video.srcObject = stream;
      } catch (err) {
        resultBox.textContent = 'Error al abrir cámara: ' + err.message;
      }
    });

    document.getElementById('capture').addEventListener('click', async () => {
      if (!video.srcObject) {
        resultBox.textContent = 'Primero haz clic en "Abrir cámara".';
        return;
      }

      const w = video.videoWidth || 640;
      const h = video.videoHeight || 480;
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, w, h);

      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92));
      const form = new FormData();
      form.append('lot_code', document.getElementById('lot').value);
      form.append('supplier_name', document.getElementById('supplier').value);
      form.append('username', document.getElementById('username').value);
      form.append('product', document.getElementById('product').value);
      form.append('image', blob, 'capture.jpg');

      try {
        const resp = await fetch('/inspect-file', { method:'POST', body: form });
        const data = await resp.json();
        if (!resp.ok) {
          resultBox.textContent = 'Error API: ' + JSON.stringify(data, null, 2);
          return;
        }

        resultBox.textContent = JSON.stringify(data, null, 2);
        annotatedImg.src = '/' + data.annotated_image_path;
      } catch (err) {
        resultBox.textContent = 'Error de red: ' + err.message;
      }
    });
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)
