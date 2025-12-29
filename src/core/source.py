from typing import Protocol, Optional
from PIL import Image
import numpy as np

class ImageSource(Protocol):
    """
    Protocol defining the contract for image sources.
    The editing engine interacts with this protocol, never concrete implementations.
    """
    def load(self) -> Image.Image:
        """
        Load and return the image.
        Returns:
            Image.Image: The loaded image in RGB mode.
        """
        ...
    
    def get_metadata(self) -> dict:
        """
        Return metadata about the image source.
        Returns:
            dict: Metadata like filename, origin type, etc.
        """
        ...

class StockImageSource:
    """
    Implementation of ImageSource for stock images.
    Can load from file path or generate placeholder images for testing.
    """
    def __init__(self, path_or_color: str = "white", size: tuple[int, int] = (512, 512)):
        """
        Initialize with a file path or a color name for generation.
        
        Args:
            path_or_color: File path to a stock image OR a color name (e.g., 'red', 'blue').
            size: Size of the generated image (width, height), only used if generating.
        """
        self.path_or_color = path_or_color
        self.size = size
        self.is_generated = self._is_color(path_or_color)

    def _is_color(self, value: str) -> bool:
        # Simple check if input looks like a color name rather than a path
        # In a real app, strict validation would be better.
        common_colors = {'white', 'black', 'red', 'green', 'blue', 'yellow', 'gray'}
        return value.lower() in common_colors

    def load(self) -> Image.Image:
        if self.is_generated:
            # Generate placeholder
            print(f"[StockImageSource] Generating {self.path_or_color} image of size {self.size}")
            return Image.new("RGB", self.size, color=self.path_or_color)
        else:
            # Load from file
            try:
                print(f"[StockImageSource] Loading from {self.path_or_color}")
                img = Image.open(self.path_or_color)
                return img.convert("RGB")
            except Exception as e:
                raise RuntimeError(f"Failed to load stock image from {self.path_or_color}: {e}")

    def get_metadata(self) -> dict:
        return {
            "type": "stock",
            "source": self.path_or_color if not self.is_generated else "generated",
            "is_generated": self.is_generated,
            "generated_size": self.size if self.is_generated else None
        }

class UploadImageSource:
    """
    Implementation of ImageSource for user-uploaded images.
    """
    def __init__(self, file_data: bytes, filename: str):
        """
        Initialize with raw file bytes.
        
        Args:
            file_data: The raw bytes of the uploaded image file.
            filename: The original filename.
        """
        self.file_data = file_data
        self.filename = filename

    def load(self) -> Image.Image:
        try:
            from io import BytesIO
            print(f"[UploadImageSource] Loading uploaded file: {self.filename}")
            img = Image.open(BytesIO(self.file_data))
            return img.convert("RGB")
        except Exception as e:
            raise ValueError(f"Failed to decode uploaded image: {e}")

    def get_metadata(self) -> dict:
        return {
            "type": "upload",
            "filename": self.filename,
            "size_bytes": len(self.file_data)
        }
