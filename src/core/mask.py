from typing import Protocol, Tuple
import numpy as np

class Mask(Protocol):
    """
    Protocol defining a selection mask.
    The mask defines the 'scope' of an edit.
    True/1 = Editable (Selected)
    False/0 = Frozen (Protected)
    """
    def to_numpy(self, shape: Tuple[int, int]) -> np.ndarray:
        """
        Generate the boolean mask array.
        
        Args:
            shape: (height, width) of the target image.
            
        Returns:
            np.ndarray: Boolean array of shape (height, width) where True means selected.
        """
        ...
    
    def get_description(self) -> str:
        """Return a human-readable description of the mask."""
        ...

class RectangularMask:
    """
    Simple rectangular selection mask.
    Defined by (x, y, width, height).
    """
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def to_numpy(self, shape: Tuple[int, int]) -> np.ndarray:
        h, w = shape
        mask = np.zeros((h, w), dtype=bool)
        
        # Clip coordinates to image bounds
        x1 = max(0, self.x)
        y1 = max(0, self.y)
        x2 = min(w, self.x + self.width)
        y2 = min(h, self.y + self.height)
        
        if x1 < x2 and y1 < y2:
            mask[y1:y2, x1:x2] = True
            
        return mask

    def get_description(self) -> str:
        return f"Rectangle(x={self.x}, y={self.y}, w={self.width}, h={self.height})"

class EverythingMask:
    """Mask that selects everything (useful for global adjustments/testing)."""
    def to_numpy(self, shape: Tuple[int, int]) -> np.ndarray:
        return np.ones(shape, dtype=bool)
    
    def get_description(self) -> str:
        return "Everything"

class BitmapMask:
    """
    Mask defined by an explicit boolean numpy array.
    Used for complex selections (e.g., object segmentation).
    """
    def __init__(self, mask_array: np.ndarray, description: str = "Bitmap Selection"):
        self.mask_array = mask_array
        self.description = description

    def to_numpy(self, shape: Tuple[int, int]) -> np.ndarray:
        # Check compatibility
        if self.mask_array.shape != shape:
            # We might need to resize if shapes mismatch? 
            # For V1 enforce strict matching to avoid errors
            raise ValueError(f"Mask shape {self.mask_array.shape} does not match image shape {shape}")
        return self.mask_array

    def get_description(self) -> str:
        return self.description
