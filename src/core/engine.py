import numpy as np
import cv2
import copy
from typing import Optional, List, Tuple, Union, Callable
from PIL import Image

from src.core.state import ImageState
from src.core.mask import Mask, BitmapMask
from src.core.layers import Layer, ImageLayer, ObjectLayer, TextLayer

class IntegrityError(Exception):
    """Raised when an edit violates the scope contract."""
    pass

class Engine:
    """
    The Core Editing Engine.
    Exposes operations that modify ImageState (Layers).
    """
    def __init__(self, state: ImageState):
        self.state = state

    def apply_scoped_edit(self, mask: Mask, new_content_generator: Union[Callable, np.ndarray], description: str):
        """
        Apply an edit strictly within the mask.
        By default, this targets the BACKGROUND Layer (Layer 0).
        """
        # Snapshot layers
        layers = copy.deepcopy(self.state.layers)
        bg_layer = layers[0]
        
        if not isinstance(bg_layer, ImageLayer):
            raise IntegrityError("Layer 0 is not an ImageLayer (Background). Cannot apply raster edit.")
            
        current_img_pil = bg_layer.image
        current_img = np.array(current_img_pil)
        h, w, c = current_img.shape
        
        # 1. Resolve Mask
        mask_boolean = mask.to_numpy((h, w))
        
        # 2. Generate New Content
        if callable(new_content_generator):
            proposed_img = new_content_generator(current_img)
        else:
            proposed_img = new_content_generator
            
        if proposed_img.shape != current_img.shape:
             # Try to match shape if alpha mismatch (RGB vs RGBA)
             pass 

        # 3. Enforce Scope
        mask_3d = np.stack([mask_boolean]*current_img.shape[-1], axis=-1)
        
        # Linear blending
        final_img = np.where(mask_3d, proposed_img, current_img)
        
        # 4. Update Layer
        bg_layer.image = Image.fromarray(final_img)
        
        # 5. Commit
        self.state.commit_edit(layers, description)

    def apply_pixel_replacement(self, mask: Mask, color: tuple[int, int, int]):
        """Simple fill."""
        def generator(img):
            res = np.zeros_like(img)
            # handle alpha if present in color or img
            if len(color) == 3 and img.shape[2] == 4:
                res[:, :] = (*color, 255)
            elif len(color) == 3:
                res[:, :] = color
            return res
            
        self.apply_scoped_edit(mask, generator, f"Fill {mask.get_description()}")

    def apply_harmonization(self, mask: Mask, brightness: float = 1.0, contrast: float = 1.0):
        """Apply brightness/contrast."""
        def harmonizer(img):
            # Convert to float
            res = img.astype(float)
            # Contrast
            res = (res - 128.0) * contrast + 128.0
            # Brightness
            res = res * brightness
            return np.clip(res, 0, 255).astype(np.uint8)
            
        self.apply_scoped_edit(mask, harmonizer, f"Harmonize (B:{brightness}, C:{contrast})")

    # --- Container Operations ---

    def lift_from_background(self, mask: np.ndarray, bbox: dict) -> str:
        """
        Extract the masked specific area from background into a new ObjectLayer.
        Inpaint the hole in the background.
        
        Args:
            mask: Boolean array (H, W) where True is the object.
            bbox: {x,y,w,h} bounding box of object.
            
        Returns:
            Layer ID of the new object.
        """
        layers = copy.deepcopy(self.state.layers)
        bg_layer = layers[0]
        
        current_img = np.array(bg_layer.image) # RGBA
        
        if np.sum(mask) < 25: 
             raise IntegrityError("Selection too small to lift (min 25px).")

        # 1. Extract Object Sprite
        # CROP to bbox to save memory/logical size
        x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
        
        # Ensure bounds
        x = max(0, x); y = max(0, y)
        w = min(w, current_img.shape[1] - x)
        h = min(h, current_img.shape[0] - y)
        
        # Crop mask and image
        crop_mask = mask[y:y+h, x:x+w]
        crop_img = current_img[y:y+h, x:x+w].copy()
        
        # Apply alpha mask to object (make non-selected pixels transparent)
        # Assuming current_img is RGBA. If RGB, add Alpha.
        if crop_img.shape[2] == 3:
            crop_img = np.dstack([crop_img, np.ones((h, w), dtype=np.uint8)*255])
            
        # Set alpha to 0 where mask is False
        crop_img[~crop_mask, 3] = 0
        
        # Create Object Layer
        sprite = Image.fromarray(crop_img)
        new_layer = ObjectLayer(sprite, x, y, name="Lifted Object")
        
        # 2. Inpaint Background
        # We need to remove the object from background.
        # Inpaint area = mask
        mask_uint8 = (mask.astype(np.uint8) * 255)
        # Dilate for clean removal
        kernel = np.ones((5, 5), np.uint8)
        mask_dilated = cv2.dilate(mask_uint8, kernel, iterations=1)
        
        # Inpaint RGB channels (Background usually has no alpha transparency, or full opaque)
        # If BG is RGBA, we just inpaint RGB and keep A=255
        bg_rgb = current_img[..., :3]
        inpainted_rgb = cv2.inpaint(bg_rgb, mask_dilated, 3, cv2.INPAINT_TELEA)
        
        # Reconstruct BG assuming opaque
        if current_img.shape[2] == 4:
             inpainted_full = np.dstack([inpainted_rgb, current_img[..., 3]])
        else:
             inpainted_full = inpainted_rgb
             
        bg_layer.image = Image.fromarray(inpainted_full)
        
        # 3. Add Layer
        layers.append(new_layer)
        
        self.state.commit_edit(layers, "Lift Object from Background")
        return new_layer.id

    def update_layer(self, layer_id: str, **kwargs):
        """
        Update properties of a layer (x, y, scale, text, font...).
        """
        layers = copy.deepcopy(self.state.layers)
        
        layer = next((l for l in layers if l.id == layer_id), None)
        if not layer:
            raise ValueError(f"Layer {layer_id} not found")
            
        desc_parts = []
        
        if 'dx' in kwargs and 'dy' in kwargs:
            # Move
            if hasattr(layer, 'x'):
                layer.x += kwargs['dx']
                layer.y += kwargs['dy']
                desc_parts.append(f"Make Move ({kwargs['dx']}, {kwargs['dy']})")
                
        if 'text' in kwargs and hasattr(layer, 'text'):
            layer.text = kwargs['text']
            # Recompute name
            layer.name = f"Text: {kwargs['text'][:10]}"
            desc_parts.append("Edit Text")

        if 'font_size' in kwargs and hasattr(layer, 'font_size'):
            layer.font_size = kwargs['font_size']
            desc_parts.append("Resize Font")
            
        if 'font_color' in kwargs and hasattr(layer, 'font_color'):
            layer.font_color = kwargs['font_color']
            desc_parts.append("Color Font")
            
        if not desc_parts:
            desc_parts.append("Update Layer")
            
        self.state.commit_edit(layers, ", ".join(desc_parts))

    def apply_transform(self, mask: Mask, dx: int, dy: int):
        """
        Legacy Move: If simple mask, tries to find object or just generic pixel move.
        For V1.1: If generic mask, we can just use pixel move on background?
        Or we can try to LIFT the area first?
        
        Let's implement the generic pixel move on Background Layer for backward compat.
        Currently 'Move' tool uses this.
        """
        # ... logic as before but targeting Layer 0 ...
        # NOTE: Since we have valid masking logic in `apply_scoped_edit`, 
        # implementing `apply_transform` using `lift_from_background` is BETTER?
        # BUT `apply_transform` was "copy paste move". "Lift" is "Cut and Inpaint".
        # "Lift" is cleaner. Let's redirect `apply_transform` to "Lift & Move" if it's a small area?
        # Wait, the user manual move tool might be dragging a selection.
        # Let's keep the old logic but adapted to Layer 0.
        
        layers = copy.deepcopy(self.state.layers)
        bg_layer = layers[0]
        current_img = np.array(bg_layer.image)
        h, w, c = current_img.shape
        
        src_mask = mask.to_numpy((h, w))
        
        # Extract, Shift, Paste
        # ... (Old implementation adapted) ...
        # For brevity and robustness, I will just use the old implementation logic here
        
        ys, xs = np.where(src_mask)
        if len(ys) == 0: return

        # Target coords
        yt = ys + dy
        xt = xs + dx
        
        # Valid
        valid = (yt >= 0) & (yt < h) & (xt >= 0) & (xt < w)
        ys_v, xs_v, yt_v, xt_v = ys[valid], xs[valid], yt[valid], xt[valid]
        
        # New Image
        new_img = current_img.copy()
        
        # Clear source (Black/Void)
        new_img[src_mask] = 0 # Or inpaint? Old was void. Keep void for consistency.
        
        # Write Dest
        new_img[yt_v, xt_v] = current_img[ys_v, xs_v]
        
        bg_layer.image = Image.fromarray(new_img)
        self.state.commit_edit(layers, f"Move Selection ({dx}, {dy})")

    def apply_inpainting(self, mask: np.ndarray, description: str = "Magic Remove", dilate_pixels: int = 5):
        """Inpaint background layer."""
        # Wrapper around apply_scoped_edit with inpaint generator
        
        # 1. Dilate
        mask_uint8 = (mask.astype(np.uint8) * 255)
        if dilate_pixels > 0:
            kernel = np.ones((dilate_pixels, dilate_pixels), np.uint8)
            mask_uint8 = cv2.dilate(mask_uint8, kernel, iterations=1)
        
        mask_bool = mask_uint8 > 127
        
        def generator(img):
            # RGB Only for cv2.inpaint
            rgb = img[..., :3]
            inpainted = cv2.inpaint(rgb, mask_uint8, 3, cv2.INPAINT_TELEA)
            # Restore alpha if needed
            if img.shape[2] == 4:
                return np.dstack([inpainted, img[..., 3]])
            return inpainted
            
        self.apply_scoped_edit(BitmapMask(mask_bool, "Inpaint"), generator, description)

    def lift_text_from_background(self, mask: np.ndarray, bbox: dict, text_content: str, font_props: dict) -> str:
        """
        Lift text into a TextLayer.
        """
        layers = copy.deepcopy(self.state.layers)
        bg_layer = layers[0]
        
        if np.sum(mask) < 50:
             raise IntegrityError("Text selection too small.")

        # 1. Create Text Layer
        new_layer = TextLayer(
            text=text_content,
            font_size=font_props.get('font_size', 20),
            font_color=font_props.get('font_color', (0,0,0)),
            x=bbox['x'],
            y=bbox['y'],
            font_family=font_props.get('font_family', 'arial.ttf')
        )
        
        # 2. Inpaint Background (Remove original text pixels)
        mask_uint8 = (mask.astype(np.uint8) * 255)
        # Dilate text mask usually needs more dilation as text is thin
        kernel = np.ones((3, 3), np.uint8) 
        mask_dilated = cv2.dilate(mask_uint8, kernel, iterations=2) # 2 iters
        
        current_img = np.array(bg_layer.image)
        rgb = current_img[..., :3]
        inpainted_rgb = cv2.inpaint(rgb, mask_dilated, 3, cv2.INPAINT_TELEA)
        
        if current_img.shape[2] == 4:
             inpainted_full = np.dstack([inpainted_rgb, current_img[..., 3]])
        else:
             inpainted_full = inpainted_rgb
             
        bg_layer.image = Image.fromarray(inpainted_full)
        
        # 3. Add Layer
        layers.append(new_layer)
        
        
        self.state.commit_edit(layers, f"Lift Text: {text_content[:10]}")
        return new_layer.id

    def add_object_layer(self, image: Image.Image, x: int, y: int, name: str = "New Object") -> str:
        """Add a new external object as a layer."""
        layers = copy.deepcopy(self.state.layers)
        
        # Default scale? 1.0
        # If image is huge, maybe downscale?
        # For V1, keep 1.0
        
        new_layer = ObjectLayer(image, x, y, name=name)
        layers.append(new_layer)
        
        self.state.commit_edit(layers, f"Add Object: {name}")
        return new_layer.id

    def replace_layer_content(self, layer_id: str, new_image: Image.Image):
        """
        Replace the image content of a layer.
        Attempts to preserve the visual bounds of the previous object.
        """
        layers = copy.deepcopy(self.state.layers)
        layer = next((l for l in layers if l.id == layer_id), None)
        
        if not layer:
            raise ValueError("Layer not found")
            
        if isinstance(layer, ObjectLayer):
            # Calculate current visual size
            old_w = layer.image.width * layer.scale
            old_h = layer.image.height * layer.scale
            
            # Update image
            # Ensure RGBA
            if new_image.mode != 'RGBA':
                new_image = new_image.convert('RGBA')
            
            layer.image = new_image
            
            # Update scale to match old visual size roughly?
            # Or just reset scale?
            # "Preserve Context" implies fitting into the slot.
            # Let's fit to the largest dim.
            
            scale_x = old_w / new_image.width
            scale_y = old_h / new_image.height
            
            # Use uniform scaling to fit
            new_scale = min(scale_x, scale_y)
            layer.scale = new_scale
            
            self.state.commit_edit(layers, "Replace Object Content")
        elif isinstance(layer, ImageLayer):
            # Background replacement?
            if new_image.mode != 'RGBA':
                new_image = new_image.convert('RGBA')
            layer.image = new_image
            self.state.commit_edit(layers, "Replace Background")
