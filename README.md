# Simbli Image Editing V1

A correctness-first image editing engine proving the "Simbli Contract":
> "Only what the user selects changes. Everything else remains untouched."

## 🏗 System Architecture & Tech Stack

Simbli V1 is built on a Layered Architecture designed for non-destructive editing and rigorous state management.

### **Core Stack**
| Component | Technology | Role in V1 |
|-----------|------------|------------|
| **Language** | **Python 3.11+** | Backend logic, type safety, and extensive ecosystem for image processing. |
| **Package Manager** | **uv** | Ultra-fast dependency resolution and environment management. |
| **Web Framework** | **FastAPI** | High-performance, async REST API for serving the engine. |
| **Server** | **Uvicorn** | ASGI server to run the FastAPI application. |

### **Image & AI Engine**
| Library | Purpose | Why for V1? |
|---------|---------|-------------|
| **Pillow (PIL)** | Image I/O, Layer Compositing | Standard for basic raster operations; handles the core `ImageState`. |
| **NumPy** | Mask Management | Efficient boolean algebra for complex selections and masks. |
| **OpenCV (`cv2`)** | Inpainting (`cv2.inpaint`) | fast, reliable object removal (NS/Telea algorithms) without heavy generative models. |
| **Torch / Torchvision** | AI Inference | Runtime for the Mask R-CNN object detection model. |
| **EasyOCR** | Text Detection | Robust, off-the-shelf text localization and recognition. |

### **Frontend**
- **Vanilla JS / HTML5 / CSS3**: A lightweight, no-build UI to verify API functionality directly.
- **Canvas API**: Renders the composite image and handles user interaction (selection, dragging).

---

## 🧩 Key Architecture Concepts

1.  **ImageState**: The single source of truth. Manages `ImageVersion`s for Undo/Redo history.
2.  **Layered System**: 
    - **Background**: The base raster image.
    - **ObjectLayer**: Movable, scalable sprites lifted from the background.
    - **TextLayer**: Editable text regions with font metadata (Family, Size, Color).
3.  **Engine**: The transactional logic layer. Executes atomic operations (e.g., `lift`, `move`, `replace`) and ensures integrity constraints (e.g., minimum selection size).
4.  **Detector**: An abstraction over AI models (`Mask R-CNN`, `EasyOCR`) to analyze image content and provide semantic masks.

---

## 🔌 API Endpoints
The engine exposes a RESTful API for session-based editing.

### **Session & State**
- `POST /stock/{color}` - Create a new session with a stock image.
- `GET /session/{id}/image` - Retrieve the current rendered state.
- `POST /session/{id}/undo` / `redo` - Travel through history.

### **Layer Management**
- `GET /session/{id}/layers` - List all layers and their properties.
- `POST /session/{id}/layers/lift` - **Magic Lift**: Extract object/text at (x,y) into a new layer.
- `PUT /session/{id}/layers/{layer_id}` - Update properties (Position, Text Content, Font Style).
- `POST /session/{id}/layers/add` - Upload an external image as a new layer.
- `POST /session/{id}/layers/{layer_id}/replace` - Replace an object's content while preserving context.

### **Tools & Magic**
- `POST /session/{id}/detect/{type}` - Run AI detection (`objects` or `text`).
- `POST /session/{id}/edit` - Apply basic edits (Fill, Harmonize) to a masked region.
- `POST /session/{id}/edit/magic-remove` - Intelligent object removal via Inpainting.

---

## 🚀 Running the Project

### 1. Environment Setup
```powershell
uv sync
```

### 2. Start the Server
```powershell
uv run uvicorn src.api.main:app --reload
```
- **UI**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Verify Correctness
Run the automated verification suite:
```powershell
uv run python verify_layers.py   # Verify Layer Logic
uv run python tests/test_e2e_logic.py # Full System Check
```
