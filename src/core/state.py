from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any
import numpy as np
from PIL import Image
import uuid
import copy
from src.core.layers import Layer, ImageLayer

@dataclass(frozen=True)
class ImageVersion:
    """
    Represents a single immutable version of the image in history.
    Stores the configuration of LAYERS.
    """
    id: str
    timestamp: datetime
    layers: List[Layer] # Immutable list of layers
    description: str
    
    @property
    def as_pil(self) -> Image.Image:
        """Composites all layers into a single image."""
        if not self.layers:
            return Image.new("RGB", (100, 100)) # Fail safe
            
        # 1. Start with first layer (usually background)
        # Note: We need a canvas size. Assume layer 0 defines it OR separate Metadata.
        # For V1, Layer 0 is always Background ImageLayer.
        
        # We render bottom-up
        base_layer = self.layers[0]
        # Base render (usually returns the image itself)
        canvas = base_layer.render(None)
        
        for layer in self.layers[1:]:
            canvas = layer.render(canvas)
            
        return canvas

    @property
    def image_data(self) -> np.ndarray:
        """Get flattened numpy array (Read-Only)."""
        img = self.as_pil
        if img.mode != "RGB":
            # For numpy processing, we usually want RGB
            img = img.convert("RGB")
        data = np.array(img)
        data.flags.writeable = False
        return data

class ImageState:
    """
    Manages the lifecycle of an image (Layer Stack), including history.
    """
    def __init__(self, initial_image: Image.Image, source_metadata: dict = None):
        """
        Initialize with the starting image as the Background Layer.
        """
        # Ensure RGB
        if initial_image.mode != "RGB":
            initial_image = initial_image.convert("RGB")
            
        # Create Background Layer
        bg_layer = ImageLayer(initial_image, "Background")
        
        genesis_version = ImageVersion(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            layers=[bg_layer],
            description="Original Image"
        )
        
        self._history: List[ImageVersion] = [genesis_version]
        self._current_index: int = 0
        self._source_metadata = source_metadata or {}

    @property
    def current_version(self) -> ImageVersion:
        """Get the currently active version node."""
        return self._history[self._current_index]

    @property
    def layers(self) -> List[Layer]:
        """Get current layers."""
        return self.current_version.layers

    @property
    def current_image_np(self) -> np.ndarray:
        """Get the current flattened image data as numpy array."""
        return self.current_version.image_data

    @property
    def can_undo(self) -> bool:
        return self._current_index > 0

    @property
    def can_redo(self) -> bool:
        return self._current_index < len(self._history) - 1

    def undo(self) -> ImageVersion:
        if not self.can_undo:
            return self.current_version
        
        self._current_index -= 1
        print(f"[ImageState] Undo -> {self.current_version.description} ({self.current_version.id[:8]})")
        return self.current_version

    def redo(self) -> ImageVersion:
        if not self.can_redo:
            return self.current_version
        
        self._current_index += 1
        print(f"[ImageState] Redo -> {self.current_version.description} ({self.current_version.id[:8]})")
        return self.current_version

    def commit_edit(self, new_layers: List[Layer], description: str) -> ImageVersion:
        """
        Commit a new version of layers.
        
        Args:
            new_layers: The new list of layers.
            description: What happened.
        """
        # Shallow copy list to enforce immutability of the container
        # Deep copy of layers?
        # Layers are mutable objects (position etc).
        # We MUST deep copy layers to ensure history doesn't change when we edit current state.
        # However, Image buffers inside layers can be shared if they are immutable/not modified.
        # `copy.deepcopy` might be too slow if it copies the 4K Image buffers.
        
        # Optimization: Manually clone layers.
        saved_layers = []
        for l in new_layers:
            # We assume layers handle their own cloning or are simple enough.
            # For now, use copy.copy (shallow) and trust that we don't mutate shared internal objects?
            # NO. `ObjectLayer` has `x`, `y`. If we change `x`, it changes in all references.
            # We need a new ObjectLayer instance.
            # `ImageLayer` has `image`. Image is not mutated mostly (unless pixel edit).
            # Let's rely on `copy.deepcopy` for now but check if it copies PIL image bytes.
            # PIL Images have a `copy()` method.
            # Let's implement `clone()` on Layers? Or use deepcopy.
            # Default pickle/deepcopy of PIL Image actually saves the bytes, efficient?
            # Actually, `copy.deepcopy` works fine for Python objects.
            saved_layers.append(copy.deepcopy(l))
            
        new_version = ImageVersion(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            layers=saved_layers,
            description=description
        )
        
        if self._current_index < len(self._history) - 1:
            print(f"[ImageState] Branching history!")
            self._history = self._history[:self._current_index + 1]
            
        self._history.append(new_version)
        self._current_index += 1
        
        print(f"[ImageState] Committed: {description} ({new_version.id[:8]}) with {len(saved_layers)} layers")
        return new_version

    def get_history_summary(self) -> List[dict]:
        return [
            {
                "index": i,
                "id": v.id,
                "description": v.description,
                "active": i == self._current_index,
                "timestamp": v.timestamp.isoformat()
            }
            for i, v in enumerate(self._history)
        ]
