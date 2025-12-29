import numpy as np
from PIL import Image

def visualize_mask(image_data: np.ndarray, mask: np.ndarray, alpha: float = 0.5) -> Image.Image:
    """
    Create a visualization of the mask overlay.
    Protected areas (False) are tinted Red.
    Selected areas (True) are clear.
    
    Args:
        image_data: RGB numpy array of image.
        mask: Boolean numpy array of same (H, W).
        alpha: Opacity of the tint.
        
    Returns:
        PIL Image for display.
    """
    if image_data.shape[:2] != mask.shape:
        raise ValueError("Image and mask shapes do not match")

    h, w, c = image_data.shape
    
    # Create an overlay: Red for protected areas
    # We want False (protected) to be Red, True (selected) to be transparent
    # So we invert the mask for the overlay alpha
    
    overlay = np.zeros_like(image_data)
    overlay[:, :] = [255, 0, 0]  # Red fill
    
    # Where mask is True (selected), we want 0 opacity (keep original)
    # Where mask is False (protected), we want alpha opacity
    
    final_image = image_data.copy().astype(float)
    
    # Apply tint to unselected regions
    # logical_not(mask) is True for unselected regions
    unselected = np.logical_not(mask)
    
    # Blend: result = original * (1 - alpha) + overlay * alpha
    # But only for unselected pixels
    # Optimized vector operation:
    
    # Expand mask to 3 channels
    unselected_3d = np.stack([unselected]*3, axis=-1)
    
    final_image[unselected_3d] = (
        final_image[unselected_3d] * (1 - alpha) + 
        overlay[unselected_3d] * alpha
    )
    
    return Image.fromarray(final_image.astype(np.uint8))
