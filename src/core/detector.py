import torch
import torchvision
from torchvision.models.detection import maskrcnn_resnet50_fpn, MaskRCNN_ResNet50_FPN_Weights
import numpy as np
from PIL import Image
import easyocr
from typing import List, Dict, Any

class Detector:
    def __init__(self):
        self._device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"[Detector] Initializing on {self._device}...")
        
        # models are lazy loaded to ensure fast module import if not used
        self._object_model = None
        self._text_reader = None

    def _get_object_model(self):
        if self._object_model is None:
            print("[Detector] Loading Mask R-CNN detected...")
            weights = MaskRCNN_ResNet50_FPN_Weights.DEFAULT
            self._object_model = maskrcnn_resnet50_fpn(weights=weights)
            self._object_model.to(self._device)
            self._object_model.eval()
            self._coco_labels = weights.meta["categories"]
        return self._object_model

    def _get_text_reader(self):
        if self._text_reader is None:
            print("[Detector] Loading EasyOCR...")
            # We enforce English for V1
            self._text_reader = easyocr.Reader(['en'], gpu=self._device.type == 'cuda')
        return self._text_reader

    def detect_objects(self, image: Image.Image, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Detect objects using Mask R-CNN.
        Returns list of {label, score, box: [x, y, w, h]}.
        """
        model = self._get_object_model()
        
        # Transform image
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        img_tensor = torchvision.transforms.functional.to_tensor(image).to(self._device)
        img_tensor = img_tensor.unsqueeze(0) # Batch dim
        
        with torch.no_grad():
            predictions = model(img_tensor)[0]
            
        results = []
        for i in range(len(predictions['boxes'])):
            score = float(predictions['scores'][i])
            if score < threshold:
                continue
                
            label_idx = int(predictions['labels'][i])
            label = self._coco_labels[label_idx] if label_idx < len(self._coco_labels) else "object"
            
            box = predictions['boxes'][i].cpu().numpy()
            # Box is x1, y1, x2, y2
            x, y, x2, y2 = box
            w = x2 - x
            h = y2 - y
            
            # Get mask if available
            mask = predictions['masks'][i, 0].cpu().numpy() # [H, W]
            # Threshold soft mask
            mask_binary = mask > 0.5
            
            results.append({
                "type": "object",
                "label": label,
                "score": score,
                "box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "mask": mask_binary  # Internal use, not JSON serializable directly. Need to handle in API layer.
            })
            
        print(f"[Detector] Found {len(results)} objects.")
        return results

    def get_object_at_point(self, image: Image.Image, x: int, y: int) -> Dict[str, Any]:
        """
        Find the top-most object at the given (x,y) coordinates.
        Returns the object dict with 'mask' (numpy bool array).
        """
        objects = self.detect_objects(image, threshold=0.3) # Lower threshold for selection
        
        # Check in reverse order (top-most first if valid)
        # Note: Mask R-CNN doesn't guarantee depth order, but usually smaller objects are checked?
        # Let's check all and pick the smallest one containing the point (usually the specific object).
        
        candidates = []
        for obj in objects:
            # Check bounding box first
            bx, by, bw, bh = obj['box']['x'], obj['box']['y'], obj['box']['w'], obj['box']['h']
            if bx <= x <= bx + bw and by <= y <= by + bh:
                # Check pixel mask
                mask = obj['mask'] # HxW
                # Ensure coords are within mask bounds
                if 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1]:
                    if mask[y, x]:
                        candidates.append(obj)
        
        if not candidates:
            return None
            
        # Return the smallest candidate by area (most specific)
        return min(candidates, key=lambda o: o['box']['w'] * o['box']['h'])

    def detect_text(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        Detect text using EasyOCR.
        Returns list of {label, score, box: [x, y, w, h]}.
        """
        reader = self._get_text_reader()
        
        # EasyOCR expects numpy array or bytes
        img_np = np.array(image)
        
        # result is list of (bbox, text, prob)
        detections = reader.readtext(img_np)
        
        results = []
        for (bbox, text, prob) in detections:
            # bbox is list of 4 points: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            # We need bounding rect
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            
            results.append({
                "type": "text",
                "label": text,
                "score": float(prob),
                "box": {
                    "x": int(x_min), 
                    "y": int(y_min), 
                    "w": int(x_max - x_min), 
                    "h": int(y_max - y_min)
                }
            })
            
        print(f"[Detector] Found {len(results)} text regions.")
        return results

    def analyze_font_properties(self, image: Image.Image, bbox: dict) -> dict:
        """
        Estimate font properties for a text region.
        """
        x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
        
        # 1. Size
        font_size = int(h * 0.8) # Heuristic
        
        # 2. Color
        # sampling center pixel might hit void.
        # Crop
        crop = image.crop((x, y, x+w, y+h))
        # Convert to numpy
        arr = np.array(crop)
        # Reshape
        pixels = arr.reshape(-1, 3 if arr.shape[2]==3 else 4)
        
        # Simple heuristic: Find color with highest contrast to boundary? 
        # Or just take the median color of pixels that are NOT the edge color?
        # Let's assume text is foreground.
        # Find dominant color via simplistic histogram or quantization
        # Very crude: Take the darker color if average is light, light if average is dark.
        # Better: Center 50% vs Edge 10%.
        
        center_color = (0, 0, 0)
        try:
             # Just take a pixel from the middle-ish
             center_pixel = arr[h//2, w//2]
             center_color = tuple(center_pixel[:3])
        except:
             pass
             
        return {
            "font_family": "arial.ttf", # Default for V1
            "font_size": max(12, font_size),
            "font_color": (int(center_color[0]), int(center_color[1]), int(center_color[2]))
        }
