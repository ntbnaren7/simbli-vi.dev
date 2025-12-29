import sys
import os
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.source import StockImageSource
from src.core.state import ImageState
from src.core.mask import RectangularMask
from src.core.engine import Engine

def test_day5_ops():
    print("=== Starting Day 5 Verification: Harmonization & Transforms ===")
    
    # 1. Setup - Gray image to easily test brightness
    source = StockImageSource(path_or_color="gray", size=(100, 100))
    state = ImageState(source.load())
    engine = Engine(state)
    
    # Verify gray is ~128
    original_val = state.current_image_np[0, 0]
    print(f"Original Pixel: {original_val}")
    
    # 2. Harmonization (Brightness)
    mask = RectangularMask(x=40, y=40, width=20, height=20)
    print("\nApplying Brightness x1.5...")
    engine.apply_harmonization(mask, brightness=1.5)
    
    current = state.current_image_np
    center = current[50, 50]
    corner = current[0, 0]
    
    print(f"Center (Harmonized): {center}")
    print(f"Corner (Untouched): {corner}")
    
    assert center[0] > original_val[0], "Center did not get brighter"
    assert np.array_equal(corner, original_val), "Outside pixel changed"
    
    # 3. Transform (Move)
    # Undo to clean slate
    state.undo()
    print("\nUndone to clean slate.")
    
    # Let's paint the center red so we can see it move
    engine.apply_pixel_replacement(mask, (255, 0, 0))
    print("Painted center RED.")
    
    # Now move it RIGHT by 20px
    # Original X: 40-60. New X: 60-80.
    print("Moving RED box +20 pixels right...")
    engine.apply_transform(mask, dx=20, dy=0)
    
    current_moved = state.current_image_np
    
    # Check OLD position (should be Black hole)
    # Center of old pos: 50, 50
    old_spot = current_moved[50, 50]
    print(f"Old Spot (50,50): {old_spot}")
    assert np.array_equal(old_spot, [0, 0, 0]), "Old spot is not empty/black!"
    
    # Check NEW position
    # Center of new pos: 50, 50+20 = 70
    new_spot = current_moved[50, 70]
    print(f"New Spot (50,70): {new_spot}")
    assert np.array_equal(new_spot, [255, 0, 0]), "New spot does not contain the object!"
    
    # Check Integrity (Far corner)
    far_corner = current_moved[0, 0]
    assert np.array_equal(far_corner, original_val), "Far corner changed!"

    print("=== Day 5 Verification Successful ===")

if __name__ == "__main__":
    test_day5_ops()
