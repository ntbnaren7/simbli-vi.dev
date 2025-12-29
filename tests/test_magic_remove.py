import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
import numpy as np
from src.api.main import app
from src.core.detector import Detector

# Mock Detector to avoid loading heavy models during test
original_get_object_at_point = Detector.get_object_at_point

def mock_get_object_at_point(self, image, x, y):
    # Create a dummy object at (x,y)
    # Let's assume there is a 50x50 square at (100, 100)
    if 100 <= x <= 150 and 100 <= y <= 150:
        mask = np.zeros((image.height, image.width), dtype=bool)
        mask[100:150, 100:150] = True
        return {
            "type": "object",
            "label": "test_box",
            "score": 0.99,
            "box": {"x": 100, "y": 100, "w": 50, "h": 50},
            "mask": mask
        }
    return None

@pytest.fixture
def client_with_mock():
    # Patch Detector
    Detector.get_object_at_point = mock_get_object_at_point
    client = TestClient(app)
    yield client
    # Restore
    Detector.get_object_at_point = original_get_object_at_point

def test_magic_remove_flow(client_with_mock):
    # 1. Create session with gray image
    res = client_with_mock.post("/stock/gray")
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    
    # 2. Add an object to the image manualy via "fill" (to have something to remove)
    # Wait, we are mocking detection, so we can just pretend something is there.
    # But for visual verification (inpainting), we should have actual distinct pixels.
    # Let's paint a red square at 100,100 first
    client_with_mock.post(f"/session/{session_id}/edit", json={
        "operation": "fill",
        "mask": {"type": "rect", "x": 100, "y": 100, "width": 50, "height": 50},
        "params": {"color": [255, 0, 0]} # Red
    })
    
    # Verify it is red
    res_img = client_with_mock.get(f"/session/{session_id}/image")
    img_before = Image.open(res_img)
    # Check center pixel
    assert img_before.getpixel((125, 125)) == (255, 0, 0)
    
    # 3. Magic Remove (Mock detector says there is an object there)
    res_remove = client_with_mock.post(f"/session/{session_id}/edit/magic-remove", json={
        "x": 125, "y": 125
    })
    assert res_remove.status_code == 200
    assert "Removed test_box" in res_remove.json()["message"]
    
    # 4. Verify Red Square is Gone (Inpainted)
    # Since background was Gray (128,128,128), inpainting should restore it to approx gray.
    res_img_after = client_with_mock.get(f"/session/{session_id}/image")
    img_after = Image.open(res_img_after)
    pixel = img_after.getpixel((125, 125))
    
    # Should NOT be Red (255, 0, 0)
    assert pixel != (255, 0, 0)
    
    # Should be close to Gray (128, 128, 128)
    # Allow some variance due to inpainting noise
    print(f"Inpainted Pixel: {pixel}")
    assert abs(pixel[0] - 128) < 20 # Tolerance
    assert abs(pixel[1] - 128) < 20
    assert abs(pixel[2] - 128) < 20
