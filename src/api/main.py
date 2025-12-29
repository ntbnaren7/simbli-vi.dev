from fastapi import FastAPI, UploadFile, HTTPException, Depends
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional, Tuple
import io
import uuid
import numpy as np
from PIL import Image

from src.core.source import StockImageSource, UploadImageSource
from src.core.state import ImageState
from src.core.engine import Engine, IntegrityError
from src.core.mask import RectangularMask, Mask
from src.core.detector import Detector

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(title="Simbli Image Editing V1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store for V1
# session_id -> ImageState
sessions: Dict[str, ImageState] = {}

class SessionResponse(BaseModel):
    session_id: str
    message: str

class DetectionResponse(BaseModel):
    items: list

class HistoryItem(BaseModel):
    index: int
    id: str
    description: str
    active: bool
    timestamp: str

class MaskConfig(BaseModel):
    type: str # "rect"
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

class EditParams(BaseModel):
    # Union of all possible params for V1
    color: Optional[tuple[int, int, int]] = None
    brightness: Optional[float] = 1.0
    contrast: Optional[float] = 1.0
    dx: Optional[int] = 0
    dy: Optional[int] = 0

class EditRequest(BaseModel):
    operation: str # "fill", "harmonize", "move"
    mask: MaskConfig
    params: EditParams

def get_session(session_id: str) -> ImageState:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]

@app.post("/stock/{color_or_path}", response_model=SessionResponse)
def load_stock_image(color_or_path: str):
    """Initialize a new session with a stock/generated image."""
    try:
        source = StockImageSource(color_or_path)
        img = source.load()
        state = ImageState(img, source.get_metadata())
        
        session_id = str(uuid.uuid4())
        sessions[session_id] = state
        
        return {"session_id": session_id, "message": f"Loaded stock image: {color_or_path}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/upload", response_model=SessionResponse)
async def upload_image(file: UploadFile):
    """Initialize a new session with an uploaded image."""
    try:
        contents = await file.read()
        source = UploadImageSource(contents, file.filename or "uploaded.png")
        img = source.load()
        state = ImageState(img, source.get_metadata())
        
        session_id = str(uuid.uuid4())
        sessions[session_id] = state
        
        return {"session_id": session_id, "message": "Loaded uploaded image"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/session/{session_id}/image")
def get_image(session_id: str):
    """Get the current image as PNG."""
    state = get_session(session_id)
    img = state.current_version.as_pil
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return Response(content=buf.getvalue(), media_type="image/png")

@app.get("/session/{session_id}/history")
def get_history(session_id: str):
    """Get the history stack."""
    state = get_session(session_id)
    return state.get_history_summary()

@app.post("/session/{session_id}/undo")
def undo(session_id: str):
    """Perform undo."""
    state = get_session(session_id)
    if not state.can_undo:
        raise HTTPException(status_code=400, detail="Cannot undo")
    state.undo()
    return {"message": "Undone", "current_version": state.current_version.id}

@app.post("/session/{session_id}/redo")
def redo(session_id: str):
    """Perform redo."""
    state = get_session(session_id)
    if not state.can_redo:
        raise HTTPException(status_code=400, detail="Cannot redo")
    state.redo()
    return {"message": "Redone", "current_version": state.current_version.id}

@app.post("/session/{session_id}/edit")
def apply_edit(session_id: str, request: EditRequest):
    """
    Apply an editing operation to the session.
    """
    state = get_session(session_id)
    engine = Engine(state)
    
    # 1. Build Mask
    if request.mask.type == "rect":
        mask = RectangularMask(request.mask.x, request.mask.y, request.mask.width, request.mask.height)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown mask type: {request.mask.type}")
        
    try:
        # 2. Dispatch Operation
        if request.operation == "fill":
            if not request.params.color:
                 raise HTTPException(status_code=400, detail="Color required for fill")
            engine.apply_pixel_replacement(mask, request.params.color)
            
        elif request.operation == "harmonize":
            engine.apply_harmonization(mask, request.params.brightness or 1.0, request.params.contrast or 1.0)
            
        elif request.operation == "move":
            engine.apply_transform(mask, request.params.dx or 0, request.params.dy or 0)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {request.operation}")
            
        return {
            "message": "Edit applied", 
            "operation": request.operation, 
            "version_id": state.current_version.id
        }
        
    except IntegrityError as e:
        # This catches scope leakage!
        raise HTTPException(status_code=500, detail=f"Integrity Violation: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PointRequest(BaseModel):
    x: int
    y: int

@app.post("/session/{session_id}/edit/magic-remove")
def magic_remove(session_id: str, request: PointRequest):
    """
    Remove an object at the specified point using inpainting.
    """
    state = get_session(session_id)
    detector = Detector()
    
    # 1. Find Object
    try:
        obj = detector.get_object_at_point(state.current_version.as_pil, request.x, request.y)
    except Exception as e:
        print(f"Detector failed: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

    if not obj:
        raise HTTPException(status_code=404, detail="No object found at this location")
        
    # 2. Inpaint
    engine = Engine(state)
    mask = obj['mask'] # bool numpy array
    label = obj['label']
    
    try:
        engine.apply_inpainting(mask, f"Magic Remove: {label}")
        return {"message": f"Removed {label}", "version_id": state.current_version.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/session/{session_id}/detect/objects")
def detect_objects(session_id: str):
    """Detect objects in the current image."""
    state = get_session(session_id)
    detector = Detector() # This will init lazily
    try:
        items = detector.detect_objects(state.current_version.as_pil)
        # Remove mask (numpy array) for JSON serialization
        results = []
        for item in items:
            clean_item = {k: v for k, v in item.items() if k != 'mask'}
            results.append(clean_item)
        return {"items": results}
    except Exception as e:
        print(f"Detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/{session_id}/detect/text")
def detect_text(session_id: str):
    """Detect text in the current image."""
    state = get_session(session_id)
    detector = Detector()
    try:
        items = detector.detect_text(state.current_version.as_pil)
        return {"items": items}
    except Exception as e:
        print(f"Detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}

# Static Files serving (Manual implementation to avoid aiofiles if possible, 
# but StaticFiles usually requires it? 
# actually StaticFiles relies on aiofiles? No, starlette StaticFiles does.
# Wait, strict rules: "No install dependencies".
# If I use StaticFiles, does it crash without aiofiles?
# Let's check imports. FastAPI usually pulls starlette.
# If StaticFiles fails, we can just write simple endpoints reading files.
# Let's try simple endpoints for safety to guarantee no dependency issues.

@app.get("/")
def read_index():
    return FileResponse("src/ui/index.html")

@app.get("/app.js")
def read_js():
    return FileResponse("src/ui/app.js")

@app.get("/session/{session_id}/layers")
def get_layers(session_id: str):
    state = get_session(session_id)
    return [l.get_metadata() for l in state.layers]

@app.post("/session/{session_id}/layers/lift")
def lift_content(session_id: str, request: PointRequest):
    state = get_session(session_id)
    detector = Detector()
    img = state.current_version.as_pil
    
    # 1. Check Text first (Text often overlaps objects but is more specific)
    # We need to run detection on the current composite image
    # Note: detect_text is somewhat expensive, but necessary
    text_items = detector.detect_text(img)
    target_text = None
    # Find smallest containing box
    for item in text_items:
        b = item['box']
        if b['x'] <= request.x <= b['x']+b['w'] and b['y'] <= request.y <= b['y']+b['h']:
             if target_text is None or (b['w']*b['h'] < target_text['box']['w']*target_text['box']['h']):
                 target_text = item
    
    engine = Engine(state)
    
    if target_text:
        # Use Rect mask for text
        mask = np.zeros((img.height, img.width), dtype=bool)
        bx, by, bw, bh = target_text['box']['x'], target_text['box']['y'], target_text['box']['w'], target_text['box']['h']
        # Clip
        bw = min(bw, img.width - bx)
        bh = min(bh, img.height - by)
        mask[by:by+bh, bx:bx+bw] = True
        
        font_props = detector.analyze_font_properties(img, target_text['box'])
        
        layer_id = engine.lift_text_from_background(mask, target_text['box'], target_text['label'], font_props)
        return {"message": "Lifted text", "layer_id": layer_id, "type": "text"}
        
    # 2. Check Object
    obj = detector.get_object_at_point(img, request.x, request.y)
    if obj:
        layer_id = engine.lift_from_background(obj['mask'], obj['box'])
        return {"message": "Lifted object", "layer_id": layer_id, "type": "object"}
        
    raise HTTPException(404, "Nothing found to lift")

class LayerUpdate(BaseModel):
    visible: Optional[bool] = None
    opacity: Optional[float] = None
    dx: Optional[int] = None
    dy: Optional[int] = None
    text: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[Tuple[int, int, int]] = None
    scale: Optional[float] = None

@app.put("/session/{session_id}/layers/{layer_id}")
def update_layer_endpoint(session_id: str, layer_id: str, update: LayerUpdate):
    state = get_session(session_id)
    engine = Engine(state)
    
    try:
        engine.update_layer(layer_id, **update.model_dump(exclude_unset=True))
        return {"message": "Layer updated", "version_id": state.current_version.id}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/style.css")
def read_css():
    return FileResponse("src/ui/style.css")

@app.post("/session/{session_id}/layers/add")
async def add_layer_endpoint(
    session_id: str, 
    file: UploadFile, 
    x: int = 0, 
    y: int = 0
):
    state = get_session(session_id)
    content = await file.read()
    image = Image.open(io.BytesIO(content))
    engine = Engine(state)
    layer_id = engine.add_object_layer(image, x, y, name=file.filename or "Object")
    return {"message": "Layer added", "layer_id": layer_id}

@app.post("/session/{session_id}/layers/{layer_id}/replace")
async def replace_layer_endpoint(
    session_id: str, 
    layer_id: str, 
    file: UploadFile
):
    state = get_session(session_id)
    content = await file.read()
    image = Image.open(io.BytesIO(content))
    engine = Engine(state)
    engine.replace_layer_content(layer_id, image)
    return {"message": "Layer content replaced", "version_id": state.current_version.id}
