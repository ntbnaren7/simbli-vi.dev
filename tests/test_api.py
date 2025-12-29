from fastapi.testclient import TestClient
import sys
import os
import io
from PIL import Image

# Modify path to find src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.main import app

client = TestClient(app)

def test_api_flow():
    print("=== Starting API Verification Flow ===")
    
    # 1. Health check
    response = client.get("/health")
    assert response.status_code == 200
    print("Health check passed.")

    # 2. Load Stock Image
    print("\n1. Testing Stock Image Load...")
    response = client.post("/stock/red")
    assert response.status_code == 200
    data = response.json()
    session_id = data["session_id"]
    print(f"Session created: {session_id}")

    # 3. Get Image
    print("\n2. Testing Get Image...")
    response = client.get(f"/session/{session_id}/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(response.content))
    print(f"Received image size: {img.size}")
    assert img.size == (512, 512)

    # 4. Upload Image
    print("\n3. Testing Upload...")
    # Create valid dummy image file
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "blue").save(buf, "PNG")
    buf.seek(0)
    
    files = {"file": ("test.png", buf, "image/png")}
    response = client.post("/upload", files=files)
    assert response.status_code == 200
    new_session_id = response.json()["session_id"]
    print(f"Upload session created: {new_session_id}")
    
    # Verify uploaded image
    response = client.get(f"/session/{new_session_id}/image")
    assert response.status_code == 200
    img_uploaded = Image.open(io.BytesIO(response.content))
    assert img_uploaded.size == (100, 100)
    print("Upload verification successful.")
    
    # 5. History / Undo (Mocking edit via backdoor or assumes initial state has 1 item)
    # Since we can't edit via API yet (Day 4 task), we just verify history has 1 item
    print("\n4. Testing History...")
    response = client.get(f"/session/{session_id}/history")
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 1
    assert history[0]["active"] == True
    print("History verified.")

    print("\n=== API VERIFICATION SUCCESSFUL ===")

if __name__ == "__main__":
    test_api_flow()
