from fastapi.testclient import TestClient
import sys
import os
import numpy as np
from PIL import Image
import io

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.main import app

client = TestClient(app)

def test_full_v1_flow():
    print("=== Starting V1 End-to-End Verification ===")
    
    # 1. Start Session
    print("\n1. Initializing Session (Gray Stock Image)...")
    res = client.post("/stock/gray")
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    print(f"Session ID: {session_id}")
    
    # helper to get image
    def get_img_np():
        r = client.get(f"/session/{session_id}/image")
        assert r.status_code == 200
        return np.array(Image.open(io.BytesIO(r.content)))

    initial = get_img_np()
    original_val = initial[0, 0] # Should be ~128
    print(f"Initial Pixel: {original_val}")

    # 2. Scope Definition & Fill
    # Rect at 10,10 size 20x20. Fill with Red.
    print("\n2. Applying FILL (Red) to rect(10,10,20,20)...")
    edit_req = {
        "operation": "fill",
        "mask": {"type": "rect", "x": 10, "y": 10, "width": 20, "height": 20},
        "params": {"color": [255, 0, 0]}
    }
    res = client.post(f"/session/{session_id}/edit", json=edit_req)
    assert res.status_code == 200
    
    current = get_img_np()
    assert np.array_equal(current[20, 20], [255, 0, 0]), "Fill failed inside scope"
    assert np.array_equal(current[0, 0], original_val), "Fill leaked outside scope"

    # 3. Harmonization
    # Brighten center (50,50, 20x20).
    print("\n3. Applying HARMONIZATION (Brighten x2) to rect(50,50,20,20)...")
    edit_req = {
        "operation": "harmonize",
        "mask": {"type": "rect", "x": 50, "y": 50, "width": 20, "height": 20},
        "params": {"brightness": 2.0}
    }
    res = client.post(f"/session/{session_id}/edit", json=edit_req)
    assert res.status_code == 200
    
    current = get_img_np()
    center_bright = current[60, 60]
    print(f"Brightened Pixel: {center_bright}")
    assert center_bright[0] > 200, "Harmonization failed"
    # Verify previous edit (Red) is still there
    assert np.array_equal(current[20, 20], [255, 0, 0]), "Previous edit lost!"

    # 4. Transform (Move)
    # Move the RED box (10,10,20,20) to (100, 100).
    # dx=90, dy=90.
    print("\n4. Applying TRANSFORM (Move Red Box +90,+90)...")
    edit_req = {
        "operation": "move",
        "mask": {"type": "rect", "x": 10, "y": 10, "width": 20, "height": 20},
        "params": {"dx": 90, "dy": 90}
    }
    res = client.post(f"/session/{session_id}/edit", json=edit_req)
    assert res.status_code == 200

    current = get_img_np()
    
    # Old spot should be black/void
    assert np.array_equal(current[20, 20], [0, 0, 0]), "Move failed: Old spot not cleared"
    
    # New spot should be Red
    # 10+90 = 100. Range 100-120. Check 110.
    new_spot = current[110, 110]
    # Note: If image is 512x512 (default stock).
    print(f"New Spot (110,110): {new_spot}")
    assert np.array_equal(new_spot, [255, 0, 0]), "Move failed: New spot empty"

    # 5. Undo / Redo
    print("\n5. Testing Undo/Redo Chain...")
    # Undo Move
    client.post(f"/session/{session_id}/undo")
    current = get_img_np()
    assert np.array_equal(current[20, 20], [255, 0, 0]), "Undo Move failed"
    
    # Redo Move
    client.post(f"/session/{session_id}/redo") 
    current = get_img_np()
    assert np.array_equal(current[110, 110], [255, 0, 0]), "Redo Move failed"

    print("\n=== V1 COMPLETE AND VERIFIED ===")

if __name__ == "__main__":
    test_full_v1_flow()
