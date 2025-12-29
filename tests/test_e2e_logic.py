import sys
import os
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.source import StockImageSource
from src.core.state import ImageState
from src.core.engine import Engine
from src.core.mask import RectangularMask

# Mimic the API logic directly
def test_e2e_logic():
    print("=== Starting Headless E2E Verification ===")
    
    # 1. Start Session
    print("\n1. Initializing State (Gray Stock Image)...")
    source = StockImageSource("gray")
    state = ImageState(source.load())
    engine = Engine(state)
    
    original_val = state.current_image_np[0, 0]
    print(f"Initial Pixel: {original_val}")

    # 2. Scope Definition & Fill
    print("\n2. Applying FILL (Red) to rect(10,10,20,20)...")
    mask1 = RectangularMask(x=10, y=10, width=20, height=20)
    engine.apply_pixel_replacement(mask1, (255, 0, 0))
    
    current = state.current_image_np
    assert np.array_equal(current[20, 20], [255, 0, 0]), "Fill failed"
    assert np.array_equal(current[0, 0], original_val), "Fill leaked"

    # 3. Harmonization
    print("\n3. Applying HARMONIZATION (Brighten x2) to rect(50,50,20,20)...")
    mask2 = RectangularMask(x=50, y=50, width=20, height=20)
    engine.apply_harmonization(mask2, brightness=2.0)
    
    current = state.current_image_np
    center_bright = current[60, 60]
    print(f"Brightened Pixel: {center_bright}")
    assert center_bright[0] > 200, "Harmonization failed"
    # Verify previous edit (Red) is still there
    assert np.array_equal(current[20, 20], [255, 0, 0]), "Previous edit lost!"

    # 4. Transform (Move)
    print("\n4. Applying TRANSFORM (Move Red Box +90,+90)...")
    # Move the RED box (10,10) to (100,100).
    # Since we are moving mask1 content.
    engine.apply_transform(mask1, dx=90, dy=90)

    current = state.current_image_np
    
    # Old spot should be black/void
    assert np.array_equal(current[20, 20], [0, 0, 0]), "Move failed: Old spot not cleared"
    
    # New spot should be Red
    # 10+90 = 100. Range 100-120. Check 110.
    new_spot = current[110, 110]
    print(f"New Spot (110,110): {new_spot}")
    assert np.array_equal(new_spot, [255, 0, 0]), "Move failed: New spot empty"

    # 5. Undo / Redo
    print("\n5. Testing Undo/Redo Chain...")
    
    # Undo Move
    state.undo()
    current = state.current_image_np
    # Should be back to red at 20,20
    assert np.array_equal(current[20, 20], [255, 0, 0]), "Undo Move failed (Old spot not restored)"
    # New spot should be EMPTY (gray? No, original was gray).
    # Wait, before the move, 110,110 was gray.
    assert np.array_equal(current[110, 110], original_val), "Undo Move failed (New spot not restored)"
    
    # Redo Move
    state.redo()
    current = state.current_image_np
    assert np.array_equal(current[110, 110], [255, 0, 0]), "Redo Move failed"

    print("\n=== E2E Logic Verified ===")

if __name__ == "__main__":
    test_e2e_logic()
