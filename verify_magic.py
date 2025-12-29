from src.api.main import app
from fastapi.testclient import TestClient
from src.core.detector import Detector
import numpy as np

# Mock
def mock_get_object_at_point(self, image, x, y):
    print("Mock Detector Called!")
    # Create valid mask
    mask = np.zeros((image.height, image.width), dtype=bool)
    mask[40:60, 40:60] = True # Top left square
    return {
        "type": "object", 
        "label": "test_obj", 
        "box": {"x":40,"y":40,"w":20,"h":20},
        "mask": mask
    }

Detector.get_object_at_point = mock_get_object_at_point

try:
    client = TestClient(app)
    # 1. Create Session
    res = client.post("/stock/gray")
    if res.status_code != 200:
        print("Failed to create session")
        exit(1)
    
    sid = res.json()["session_id"]
    
    # 2. Magic Remove
    print("Calling Magic Remove...")
    res = client.post(f"/session/{sid}/edit/magic-remove", json={"x": 50, "y": 50})
    print("Response:", res.json())
    
    if res.status_code == 200 and "Removed test_obj" in res.json()["message"]:
        print("VERIFICATION SUCCESS")
    else:
        print("VERIFICATION FAILED")
except Exception as e:
    print(f"Exception: {e}")
    exit(1)
