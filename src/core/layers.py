from typing import Protocol, Tuple, Optional, Any
from PIL import Image, ImageDraw, ImageFont
import uuid
import numpy as np

class Layer(Protocol):
    """
    Protocol for a renderable layer using PIL.
    """
    id: str
    visible: bool
    opacity: float # 0.0 to 1.0
    
    def render(self, background: Image.Image) -> Image.Image:
        """Render this layer onto the background image."""
        ...
    
    def get_metadata(self) -> dict:
        """Return layer properties for serialization."""
        ...

class BaseLayer:
    def __init__(self, visible: bool = True, opacity: float = 1.0):
        self.id = str(uuid.uuid4())
        self.visible = visible
        self.opacity = opacity

class ImageLayer(BaseLayer):
    """
    Represents the background/base image or a full-size raster layer.
    """
    def __init__(self, image: Image.Image, name: str = "Background"):
        super().__init__()
        self.image = image.convert("RGBA")
        self.name = name

    def render(self, background: Optional[Image.Image] = None) -> Image.Image:
        if not self.visible:
            return background if background else Image.new("RGBA", self.image.size)
        
        # If background is provided, composite on top of it
        # If no background, this IS the background
        if background:
            return Image.alpha_composite(background, self.image)
        return self.image

    def get_metadata(self) -> dict:
        return {
            "id": self.id,
            "type": "image",
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity
        }

class ObjectLayer(BaseLayer):
    """
    A standalone object (sprite) with position and scale.
    """
    def __init__(self, image: Image.Image, x: int, y: int, name: str = "Object"):
        super().__init__()
        self.image = image.convert("RGBA")
        self.x = x
        self.y = y
        self.name = name
        self.scale = 1.0

    def render(self, background: Image.Image) -> Image.Image:
        if not self.visible:
            return background

        # Resize if scale != 1.0
        target_img = self.image
        if self.scale != 1.0:
            w, h = target_img.size
            new_size = (int(w * self.scale), int(h * self.scale))
            target_img = target_img.resize(new_size, Image.Resampling.LANCZOS)

        # Create a temporary canvas matching background to composite
        # (This is inefficient for many layers, but safe for PIL compositing)
        layer_canvas = Image.new("RGBA", background.size, (0, 0, 0, 0))
        layer_canvas.paste(target_img, (self.x, self.y), target_img if target_img.mode == 'RGBA' else None)
        
        return Image.alpha_composite(background, layer_canvas)

    def get_metadata(self) -> dict:
        return {
            "id": self.id,
            "type": "object",
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity,
            "x": self.x,
            "y": self.y,
            "scale": self.scale,
            "width": self.image.width * self.scale,
            "height": self.image.height * self.scale
        }

class TextLayer(BaseLayer):
    """
    Editable text layer.
    """
    def __init__(self, text: str, font_size: int, font_color: Tuple[int, int, int], x: int, y: int, font_family: str = "arial.ttf"):
        super().__init__()
        self.text = text
        self.font_size = font_size
        self.font_color = font_color # (R, G, B)
        self.x = x
        self.y = y
        self.font_family = font_family
        self.name = f"Text: {text[:10]}"

    def render(self, background: Image.Image) -> Image.Image:
        if not self.visible:
            return background

        draw = ImageDraw.Draw(background)
        
        try:
            # Try to load font, fallback to default
            font = ImageFont.truetype(self.font_family, self.font_size)
        except:
            font = ImageFont.load_default()
            # Default font doesn't support size scaling directly usually, but PIL latest might
        
        # Draw text directly on background (or copy of it if we want functionality to not mutate input, 
        # but usage pattern expects return new image usually)
        # We should not mutate `background` in place if we follow functional style, but PIL `alpha_composite` returns new.
        # `ImageDraw` mutates. So we must copy `background` first.
        canvas = background.copy()
        draw_canvas = ImageDraw.Draw(canvas)
        
        draw_canvas.text((self.x, self.y), self.text, font=font, fill=(*self.font_color, 255))
        
        return canvas

    def get_metadata(self) -> dict:
        return {
            "id": self.id,
            "type": "text",
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity,
            "text": self.text,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "x": self.x,
            "y": self.y,
            "font_family": self.font_family
        }
