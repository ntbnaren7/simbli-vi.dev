import sys
import os
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.source import StockImageSource
from src.core.mask import RectangularMask
from src.core.debug import visualize_mask

def test_day3_mask():
    print("=== Starting Day 3 Verification ===")
    
    # 1. Load an image
    source = StockImageSource(path_or_color="green", size=(200, 200))
    img = source.load()
    img_data = np.array(img)
    
    # 2. Define a rectangular mask in the center
    # Center is 100,100. Let's make a 50x50 box at 75,75
    mask_def = RectangularMask(x=75, y=75, width=50, height=50)
    print(f"Created Mask: {mask_def.get_description()}")
    
    # 3. Generate boolean mask
    mask_np = mask_def.to_numpy(img_data.shape[:2])
    
    # Verify True counts
    expected_pixels = 50 * 50
    actual_pixels = np.sum(mask_np)
    print(f"Masked pixels: {actual_pixels} (Expected: {expected_pixels})")
    assert actual_pixels == expected_pixels, "Mask pixel count mismatch"
    
    # 4. Visualization
    print("Generating debug visualization...")
    vis = visualize_mask(img_data, mask_np, alpha=0.5)
    
    # Check pixels in visualization
    vis_data = np.array(vis)
    
    # Center pixel (Selected) should remain Green (0, 128, 0) - wait, stock green is usually 0,128,0 in PIL `Image.new`? No, "green" is usually (0, 128, 0) or (0, 255, 0).
    # StockImageSource "green" -> Image.new("RGB", ..., color="green") -> usually (0, 128, 0).
    # Let's check the center pixel of the ORIGINAL to be sure what green is.
    original_center = img_data[100, 100]
    vis_center = vis_data[100, 100]
    
    print(f"Original Center: {original_center}")
    print(f"Visualized Center: {vis_center}")
    
    # Selected area should be UNTOUCHED
    assert np.array_equal(original_center, vis_center), "Selected area was modified by visualization!"
    
    # Corner pixel (Unselected) should be TINTED RED
    # Original: Green
    # Overlay: Red
    # Result: Green * 0.5 + Red * 0.5
    original_corner = img_data[0, 0] # [0, 128, 0] approx
    vis_corner = vis_data[0, 0]
    
    print(f"Original Corner: {original_corner}")
    print(f"Visualized Corner: {vis_corner}")
    
    # Just check it changed
    assert not np.array_equal(original_corner, vis_corner), "Unselected area was NOT modified!"
    # Check it got redder
    assert vis_corner[0] > original_corner[0], "Unselected area did not get red tint"

    print("=== Day 3 Verification Successful ===")

if __name__ == "__main__":
    test_day3_mask()
