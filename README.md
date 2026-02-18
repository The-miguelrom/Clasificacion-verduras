# MVP IA para Clasificación de Calidad de Tomate con Cámara Fija

Este repositorio propone y deja **implementado un MVP funcional** para una empresa empacadora/exportadora que inspecciona tomate en estación fija.

## 1) Alcance del MVP (y fuera de alcance)

### Alcance (MVP sí incluye)
- Una sola verdura objetivo: **tomate** (escalable a otras verduras).
- Estación de inspección fija con:
  - cámara USB/IP fija,
  - fondo liso,
  - iluminación constante,
  - marca de posición del producto.
- Clasificación de calidad en 3 categorías:
  - **A** = supermercado/exportación,
  - **B** = mercado local,
  - **C** = rechazo.
- Detección de defectos visibles (2–3 para MVP):
  - `mancha`,
  - `magulladura`,
  - `podrido_rajadura`.
- Clasificación de calibre `S/M/L` por tamaño aparente; opción de calibración a cm con **marcador ArUco**.
- Trazabilidad completa por lote (metadatos + imagen original y anotada + confianza + usuario).
- API mínima operativa (`/inspect`, `/inspections`, `/reports`) con FastAPI.

### Fuera de alcance (fase posterior)
- Control de robots/actuadores para descarte automático.
- Multi-cámara 360°.
- Reentrenamiento automático en producción (MLOps completo).
- Integración directa con ERP/WMS corporativo (se define interfaz, pero no se implementa full).

---

## 2) Requerimientos

### Funcionales
- RF1: Registrar lote, proveedor/finca, producto y operario antes de inspeccionar.
- RF2: Capturar imagen desde cámara fija o recibir imagen por API.
- RF3: Detectar defectos visibles (bbox o máscara) y devolver score por defecto.
- RF4: Determinar calidad final `A/B/C` con reglas de negocio + IA.
- RF5: Determinar calibre `S/M/L`.
- RF6: Guardar inspección e imágenes (original/anotada) para trazabilidad.
- RF7: Consultar historial por filtros (fecha, lote, proveedor, calidad, usuario).
- RF8: Generar resumen KPI para dashboard.

### No funcionales
- RNF1: Tiempo de respuesta objetivo por inspección: `< 1.5s` en hardware recomendado.
- RNF2: Disponibilidad local de operación (sin internet obligatoria).
- RNF3: Seguridad con autenticación por rol y bitácora de acciones.
- RNF4: Diseño modular para reemplazar modelo IA sin romper API.
- RNF5: Bajo costo y mantenimiento simple en bodega.

---

## 3) Arquitectura propuesta (diagrama textual)

```text
[Cámara fija USB/IP]
        |
        v
[Servicio de Captura: OpenCV/GStreamer]
        |
        v
[Backend API FastAPI]
   |        |         \
   |        |          -> [Almacenamiento imágenes: local/NAS/S3]
   |        v
   |   [Servicio de Inferencia IA]
   |      - YOLOv8/YOLOv8-seg (defectos)
   |      - Regla de negocio + calibre
   |
   v
[PostgreSQL/MySQL]
   |
   v
[Dashboard BI: Metabase / Power BI / Looker Studio / Web]
```

**Patrón recomendado:** monolito modular en MVP (API + inferencia en mismo servicio), separable a microservicios al escalar.

---

## 4) Diseño de base de datos (lógico)

### Tabla `suppliers`
- `id` (PK)
- `name`
- `farm_code`
- `country`
- `active`
- `created_at`

### Tabla `users`
- `id` (PK)
- `username`
- `password_hash`
- `role` (`operator`, `supervisor`, `admin`)
- `full_name`
- `active`
- `created_at`

### Tabla `lots`
- `id` (PK)
- `lot_code` (único)
- `supplier_id` (FK -> suppliers)
- `product` (ej. `tomate`)
- `harvest_date`
- `received_at`
- `notes`

### Tabla `inspections`
- `id` (PK)
- `lot_id` (FK -> lots)
- `user_id` (FK -> users)
- `inspected_at`
- `quality_class` (`A/B/C`)
- `size_class` (`S/M/L`)
- `confidence` (0..1)
- `decision_reason`
- `defect_summary` (json/text)

### Tabla `inspection_images`
- `id` (PK)
- `inspection_id` (FK -> inspections)
- `original_path`
- `annotated_path`
- `storage_type` (`local`, `nas`, `s3`)
- `checksum`

### Tabla `defect_catalog`
- `id` (PK)
- `code` (`mancha`, `magulladura`, `podrido_rajadura`)
- `severity_weight`
- `auto_reject`

### Tabla `inspection_defects`
- `id` (PK)
- `inspection_id` (FK -> inspections)
- `defect_id` (FK -> defect_catalog)
- `score`
- `bbox_or_mask` (json)
- `area_ratio`

### Tabla `audit_log`
- `id` (PK)
- `user_id` (FK -> users)
- `action`
- `entity`
- `entity_id`
- `details`
- `created_at`

---

## 5) Flujo de usuario (operación)

1. Operario inicia sesión.
2. Selecciona o crea lote (`lote`, `proveedor`, `producto=tomate`).
3. Coloca tomate en marca de posición de la estación.
4. Sistema captura imagen (o recibe imagen desde endpoint).
5. Servicio IA detecta defectos y estima calibre.
6. Reglas de negocio consolidan resultado final `A/B/C`.
7. UI muestra imagen anotada + defectos + confianza + calibre.
8. Operario confirma/ajusta (según permisos) y guarda.
9. Se registra trazabilidad completa.
10. Supervisor consulta historial y dashboard KPI.

---

## 6) Modelo de IA recomendado

### Enfoque recomendado para MVP
- **Defectos:** `YOLOv8` (detección) o `YOLOv8-seg` (segmentación).
  - Si se necesita precisión de área de defecto, usar `YOLOv8-seg`.
  - Para arrancar rápido, usar `YOLOv8` detección.
- **Calidad A/B/C:** dos alternativas:
  1. Directa por clasificación (EfficientNet/MobileNet), o
  2. **Híbrida (recomendada MVP):** calidad final derivada de defectos detectados + calibre + umbrales.
- **Calibre S/M/L:**
  - sin regla física: umbrales en píxeles,
  - con cm reales: marcador ArUco para convertir px→cm.

### Justificación técnica
- Dataset pequeño (300–800 imágenes): modelo liviano + reglas explícitas mejora defendibilidad.
- Detección de defectos ofrece explicabilidad visual para auditoría y aceptación de negocio.

### Métricas clave
- Clasificación calidad: `accuracy`, `precision`, `recall`, `F1`, matriz de confusión.
- Detección: `mAP@50`, `mAP@50-95`, `precision`, `recall` por clase.
- Operación: tiempo inferencia, tasa de rechazo por lote/proveedor.
- Umbral de confianza inicial sugerido: `0.45–0.60` (ajustar por validación).

---

## 7) Plan de dataset y etiquetado (300–800 imágenes)

### Captura consistente
- Cámara fija a distancia constante.
- Luz LED difusa uniforme (evitar sombras duras).
- Fondo mate de alto contraste con tomate.
- Marca de posición en mesa.
- Incluir variación controlada: madurez, suciedad, tamaños, defectos reales.

### Etiquetas
- `defectos`: mancha, magulladura, podrido_rajadura.
- `calidad_global`: A/B/C.
- `calibre`: S/M/L.
- `metadatos`: lote, proveedor, fecha, turno, operario.

### Herramientas
- LabelImg (bbox), Roboflow o Label Studio.

### Estrategia de partición y desbalance
- Split estratificado: `70/15/15` (train/val/test).
- Aumentación: brillo, contraste, rotación leve, blur ligero.
- Oversampling para clases minoritarias (ej. podredumbre).
- Validación cruzada ligera si dataset muy pequeño.

---

## 8) API mínima

### `POST /inspect`
Entrada (multipart o JSON + imagen):
- `lot_code`, `supplier_name`, `product`, `username`
- `captured_image` (archivo opcional)
- `manual_size_px` (opcional para demo)
- `detected_defects` (opcional para pruebas sin modelo)

Salida:
- `quality_class`, `size_class`, `confidence`
- `defects[]`
- `annotated_image_path`
- `inspection_id`

### `GET /inspections?filters`
- filtros: fecha, proveedor, lote, calidad, usuario
- retorna lista paginada

### `GET /reports`
- resumen por fecha/proveedor/lote
- KPIs: rechazo %, defectos frecuentes, volumen inspeccionado

---

## 9) Pantallas del MVP

1. **Login** (rol + acceso).
2. **Nueva inspección** (lote, proveedor, captura).
3. **Resultado** (imagen marcada, defectos, calidad, calibre, confianza).
4. **Historial por lote** (tabla + detalle por inspección).
5. **Dashboard KPI**:
   - `% rechazo (C)`
   - defectos más frecuentes
   - ranking de proveedores
   - tendencia semanal A/B/C

---

## 10) Reglas de negocio (ejemplo base)

- Si existe `podrido_rajadura` con score >= umbral => **C** automático.
- Si hay `mancha` o `magulladura` moderada y tamaño válido => **B**.
- Si no hay defectos relevantes y tamaño en rango => **A**.
- Si confianza IA < umbral mínimo => marcar como “revisión supervisor”.

---

## 11) Seguridad y auditoría

- Roles:
  - `operario`: captura y registro.
  - `supervisor`: revisión/corrección y reportes.
  - `admin`: usuarios, catálogos y configuración.
- Bitácora obligatoria:
  - login/logouts,
  - cambios de clasificación,
  - edición de lotes/proveedores,
  - exportaciones de reportes.
- Recomendado: JWT + expiración + hash seguro de contraseña (bcrypt/argon2).

---

## 12) Cronograma sugerido (8 semanas)

- **Semana 1:** levantamiento funcional + diseño estación física.
- **Semana 2:** captura piloto y definición de etiquetas.
- **Semana 3:** etiquetado inicial + baseline modelo.
- **Semana 4:** API de inferencia + reglas de negocio.
- **Semana 5:** persistencia, trazabilidad y endpoints de consulta.
- **Semana 6:** UI básica (nueva inspección + historial + login).
- **Semana 7:** dashboard KPI + pruebas de campo.
- **Semana 8:** ajuste final, documentación y defensa.

---

## 13) Riesgos y mitigación

- **Luz variable:** caja de luz / cortinas difusoras.
- **Variación de producto:** muestreo diverso por proveedor/temporada.
- **Fondo sucio:** protocolo de limpieza por turno.
- **Ángulos inconsistentes:** soporte fijo + guía de colocación.
- **Sesgo de datos:** monitoreo por proveedor y recalibración periódica.

---

## 14) Stack final propuesto + despliegue

### Stack MVP recomendado
- **Captura:** OpenCV (Python) con soporte USB/IP.
- **Backend/API:** FastAPI.
- **IA:** Ultralytics YOLOv8 (`n` o `s`) + reglas de negocio.
- **DB:** PostgreSQL (o SQLite para demo local).
- **Dashboard:** Metabase conectado a PostgreSQL.
- **Storage:** carpeta local/NAS; opcional MinIO/S3.

### Despliegue Opción A (local bodega)
- PC industrial o workstation con Linux/Windows.
- Docker Compose (api + db + metabase).
- Opera offline y sincroniza reportes cuando haya red.

### Despliegue Opción B (híbrido/nube)
- Captura local + API local; replicación de BD/imágenes a nube.
- Reportería centralizada multi-planta.

### Hardware mínimo sugerido
- **CPU only (arranque):** i5/Ryzen5, 16GB RAM, SSD 512GB.
- **Con GPU (mejor latencia):** NVIDIA RTX 3050/3060 o Jetson Orin (según presupuesto).
- Cámara: webcam 1080p con enfoque fijo o cámara IP 2MP+.

---

## Implementación funcional incluida en este repositorio

Se incluye una API FastAPI ejecutable que simula (y permite integrar) el flujo de inspección:

- Reglas A/B/C implementadas.
- Clasificación de calibre S/M/L.
- Persistencia de inspecciones en SQLite.
- Endpoints `/inspect`, `/inspections`, `/reports`.

### Ejecución rápida

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Documentación interactiva:
- `http://127.0.0.1:8000/docs`
