import sys
import os
import numpy as np

# Add project root to path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.source import StockImageSource
from src.core.state import ImageState

def test_day1_flow():
    print("=== Starting Day 1 Verification Flow ===")

    # 1. Load Source
    print("\n1. Loading Source...")
    source = StockImageSource(path_or_color="blue", size=(100, 100))
    initial_img = source.load()
    print(f"Loaded image size: {initial_img.size} mode: {initial_img.mode}")

    # 2. Init State
    print("\n2. Initializing ImageState...")
    state = ImageState(initial_img, source.get_metadata())
    print(f"Current version: {state.current_version.description}")
    
    # Check initial pixel
    top_left = state.current_image_np[0, 0]
    print(f"Initial top-left pixel: {top_left}")
    assert np.array_equal(top_left, [0, 0, 255]), "Expected blue pixel"

    # 3. Perform Edit
    print("\n3. Performing Edit (Green Patch)...")
    
    # Create new buffer based on old one
    current = state.current_image_np
    new_data = current.copy()
    
    # Make a green patch
    new_data[10:20, 10:20] = [0, 255, 0]
    
    state.commit_edit(new_data, "Applied Green Patch")
    
    # Verify change
    patch_pixel = state.current_image_np[15, 15]
    print(f"Patch pixel: {patch_pixel}")
    assert np.array_equal(patch_pixel, [0, 255, 0]), "Expected green pixel in patch"
    print(f"Current version: {state.current_version.description}")

    # 4. Undo
    print("\n4. Testing Undo...")
    assert state.can_undo
    state.undo()
    print(f"After Undo: {state.current_version.description}")
    
    # Verify reversion
    patch_pixel_undo = state.current_image_np[15, 15]
    print(f"Patch pixel after undo: {patch_pixel_undo}")
    assert np.array_equal(patch_pixel_undo, [0, 0, 255]), "Expected blue pixel again"

    # 5. Redo
    print("\n5. Testing Redo...")
    assert state.can_redo
    state.redo()
    print(f"After Redo: {state.current_version.description}")
    
    patch_pixel_redo = state.current_image_np[15, 15]
    assert np.array_equal(patch_pixel_redo, [0, 255, 0]), "Expected green pixel again"

    print("\n=== VERIFICATION SUCCESSFUL ===")

if __name__ == "__main__":
    test_day1_flow()
