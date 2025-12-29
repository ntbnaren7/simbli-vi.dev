import sys
import os
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.source import StockImageSource
from src.core.state import ImageState
from src.core.mask import RectangularMask
from src.core.engine import Engine, IntegrityError

def test_day4_scope():
    print("=== Starting Day 4 Verification: Scoped Editing ===")
    
    # 1. Setup
    source = StockImageSource(path_or_color="blue", size=(100, 100))
    state = ImageState(source.load())
    engine = Engine(state)
    
    # 2. Define Scope (Center 20x20)
    # 100x100 image. Center is 50,50. 
    # Rect: x=40, y=40, w=20, h=20.
    mask = RectangularMask(x=40, y=40, width=20, height=20)
    
    # 3. Apply Edit: Fill with Red
    print(f"Applying RED fill to {mask.get_description()}...")
    engine.apply_pixel_replacement(mask, (255, 0, 0))
    
    # 4. Verify Scope Isolation
    current = state.current_image_np
    
    # Check INSIDE (should be Red)
    center_pixel = current[50, 50]
    print(f"Center pixel (Inside Scope): {center_pixel}")
    assert np.array_equal(center_pixel, [255, 0, 0]), "Failed to update scoped pixels!"
    
    # Check OUTSIDE (should be Blue)
    corner_pixel = current[0, 0]
    print(f"Corner pixel (Outside Scope): {corner_pixel}")
    assert np.array_equal(corner_pixel, [0, 0, 255]), "Scope Leakage: Outside pixel changed!"
    
    # 5. Integrity Check Unit Test
    # Manually trigger integrity error to prove detection works
    print("\nTesting Integrity Checker directly...")
    try:
        # Create a leaked image
        leaked = current.copy()
        leaked[0, 0] = [0, 255, 0] # Change top-left (outside mask)
        
        # Ask engine to validate
        mask_bool = mask.to_numpy((100, 100))
        engine._validate_integrity(current, leaked, mask_bool)
        
        print("!! FAILED: Integrity check missed leakage !!")
        assert False, "Integrity check failed to catch leakage"
    except IntegrityError as e:
        print(f"SUCCESS: Caught expected integrity error: {e}")

    # 6. Verify "Global Proposal" is clipped
    # If we propose a FULL GREEN image, but mask is small, only mask should turn green.
    print("\nTesting Global Proposal Clipping...")
    full_green = np.zeros_like(current)
    full_green[:] = [0, 255, 0]
    
    engine.apply_scoped_edit(mask, full_green, "Try to fill everything green")
    
    current_2 = state.current_image_np
    
    # Center should now be GREEN
    assert np.array_equal(current_2[50, 50], [0, 255, 0]), "Scoped update failed"
    # Corner should STILL be BLUE (Protected)
    assert np.array_equal(current_2[0, 0], [0, 0, 255]), "Global proposal leaked outside scope!"
    
    print("Optimization/Clipping worked.")

    print("=== Day 4 Verification Successful ===")

if __name__ == "__main__":
    test_day4_scope()
