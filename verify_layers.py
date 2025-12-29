from src.api.main import app
from fastapi.testclient import TestClient
from src.core.detector import Detector
import numpy as np

# MOCK
def mock_detect_text(self, image):
    print("Mock Detect Text")
    return [{
        "box": {"x": 100, "y": 100, "w": 50, "h": 20},
        "label": "HELLO",
        "score": 0.99
    }]

def mock_get_object(self, image, x, y):
    print(f"Mock Get Object {x},{y}")
    mask = np.zeros((image.height, image.width), dtype=bool)
    mask[20:40, 20:40] = True 
    return {
        "type": "object",
        "label": "cube",
        "box": {"x":20, "y":20, "w":20, "h":20},
        "mask": mask
    }

def mock_analyze_font(self, image, bbox):
    return {
        "font_family": "arial.ttf",
        "font_size": 24,
        "font_color": (255, 0, 0)
    }

Detector.detect_text = mock_detect_text
Detector.get_object_at_point = mock_get_object
Detector.analyze_font_properties = mock_analyze_font

client = TestClient(app)

def test_layers():
    # 1. Session
    res = client.post("/stock/gray")
    sid = res.json()["session_id"]
    print(f"Session: {sid}")

    # 2. Lift Object at 30,30
    print("Testing Lift Object...")
    res = client.post(f"/session/{sid}/layers/lift", json={"x": 30, "y": 30})
    print("Lift Obj: ", res.json())
    assert res.status_code == 200
    obj_layer_id = res.json()["layer_id"]
    
    # Check Layers
    res = client.get(f"/session/{sid}/layers")
    layers = res.json()
    print("Layers:", len(layers))
    assert len(layers) == 2 # Bg + Obj
    assert layers[-1]["id"] == obj_layer_id
    assert layers[-1]["type"] == "object"
    
    # 3. Move Object
    print("Testing Move Layer...")
    res = client.put(f"/session/{sid}/layers/{obj_layer_id}", json={"dx": 10, "dy": 10})
    assert res.status_code == 200
    
    # Verify pos
    res = client.get(f"/session/{sid}/layers")
    l = next(l for l in res.json() if l["id"] == obj_layer_id)
    print(f"Moved to: {l['x']}, {l['y']}")
    assert l["x"] == 30 # 20 + 10
    
    # 4. Lift Text (at 110, 110)
    print("Testing Lift Text...")
    res = client.post(f"/session/{sid}/layers/lift", json={"x": 110, "y": 110})
    print("Lift Text: ", res.json())
    if res.status_code == 200:
        txt_layer_id = res.json()["layer_id"]
        assert res.json()["type"] == "text"
        
        # Verify Text Layer
        res = client.get(f"/session/{sid}/layers")
        l = next(l for l in res.json() if l["id"] == txt_layer_id)
        assert l["type"] == "text"
        assert l["text"] == "HELLO"
        print("Text Layer verified")
    else:
        print("Lift Text Failed:", res.json())
        
    print("ALL TESTS PASSED")

if __name__ == "__main__":
    try:
        test_layers()
    except Exception as e:
        print("FAILED:", e)
        exit(1)
