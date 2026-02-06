"""
Computer Vision Module for TikTok AI
Object detection, scene classification, face analysis, OCR
"""

import asyncio
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False


# ==================== DATA CLASSES ====================

@dataclass
class DetectedObject:
    """Single detected object"""
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    frame_index: int = 0


@dataclass
class SceneClassification:
    """Scene classification result"""
    primary_scene: str
    confidence: float
    all_scenes: Dict[str, float] = field(default_factory=dict)


@dataclass
class FaceDetection:
    """Face detection result"""
    face_count: int
    faces: List[Dict] = field(default_factory=list)  # bbox, landmarks, expression


@dataclass
class OCRResult:
    """OCR text extraction result"""
    texts: List[str]
    confidences: List[float]
    locations: List[Tuple[int, int, int, int]]


@dataclass
class VisionResult:
    """Complete vision analysis result"""
    video_path: str
    frame_count: int
    objects: List[DetectedObject] = field(default_factory=list)
    scenes: List[SceneClassification] = field(default_factory=list)
    faces: Optional[FaceDetection] = None
    ocr: Optional[OCRResult] = None
    dominant_colors: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get analysis summary"""
        object_counts = {}
        for obj in self.objects:
            object_counts[obj.label] = object_counts.get(obj.label, 0) + 1
        
        return {
            "frames_analyzed": self.frame_count,
            "unique_objects": len(set(o.label for o in self.objects)),
            "object_counts": object_counts,
            "face_count": self.faces.face_count if self.faces else 0,
            "has_text": len(self.ocr.texts) > 0 if self.ocr else False,
            "primary_scene": self.scenes[0].primary_scene if self.scenes else "unknown"
        }


# ==================== OBJECT DETECTOR ====================

class ObjectDetector:
    """
    Object detection using YOLO
    Falls back to basic OpenCV detection if YOLO unavailable
    """
    
    # Common TikTok-relevant objects
    RELEVANT_OBJECTS = {
        'person', 'face', 'dog', 'cat', 'phone', 'laptop', 'tv',
        'bottle', 'cup', 'food', 'car', 'book', 'clock', 'sports ball'
    }
    
    def __init__(self, model_name: str = "yolov8n.pt", confidence_threshold: float = 0.5):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._initialized = False
    
    def _initialize(self):
        """Lazy model loading"""
        if self._initialized:
            return
        
        if HAS_YOLO:
            try:
                self._model = YOLO(self.model_name)
                print(f"[VISION] Loaded YOLO model: {self.model_name}")
            except Exception as e:
                print(f"[VISION] Failed to load YOLO: {e}")
        
        self._initialized = True
    
    def detect(self, frame: Any) -> List[DetectedObject]:
        """Detect objects in a single frame"""
        self._initialize()
        
        if self._model is None:
            return self._fallback_detection(frame)
        
        try:
            results = self._model(frame, verbose=False)
            
            detections = []
            for result in results:
                for box in result.boxes:
                    conf = float(box.conf)
                    if conf < self.confidence_threshold:
                        continue
                    
                    cls = int(box.cls)
                    label = result.names[cls]
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    detections.append(DetectedObject(
                        label=label,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2)
                    ))
            
            return detections
            
        except Exception as e:
            print(f"[VISION] Detection error: {e}")
            return []
    
    def _fallback_detection(self, frame: Any) -> List[DetectedObject]:
        """Simple fallback detection using OpenCV"""
        if not HAS_CV2:
            return []
        
        detections = []
        
        # Face detection using Haar cascades
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            
            for (x, y, w, h) in faces:
                detections.append(DetectedObject(
                    label="person",
                    confidence=0.7,
                    bbox=(x, y, x+w, y+h)
                ))
        except:
            pass
        
        return detections
    
    async def detect_video(
        self, 
        frames: List[Any], 
        sample_rate: int = 1
    ) -> List[DetectedObject]:
        """Detect objects across video frames"""
        all_detections = []
        
        for i, frame in enumerate(frames[::sample_rate]):
            frame_detections = self.detect(frame.data if hasattr(frame, 'data') else frame)
            
            for det in frame_detections:
                det.frame_index = i * sample_rate
                all_detections.append(det)
        
        return all_detections


# ==================== SCENE CLASSIFIER ====================

class SceneClassifier:
    """
    Scene classification for video content
    """
    
    # Scene categories relevant for TikTok
    SCENE_CATEGORIES = [
        'indoor', 'outdoor', 'bedroom', 'kitchen', 'bathroom',
        'office', 'gym', 'restaurant', 'street', 'nature',
        'beach', 'stage', 'studio', 'car'
    ]
    
    def __init__(self):
        self._model = None
    
    def classify(self, frame: Any) -> SceneClassification:
        """Classify scene in frame"""
        if not HAS_CV2:
            return SceneClassification(primary_scene="unknown", confidence=0)
        
        # Simple heuristic-based classification
        return self._heuristic_classification(frame)
    
    def _heuristic_classification(self, frame: Any) -> SceneClassification:
        """Heuristic scene classification based on color and brightness"""
        if not HAS_CV2:
            return SceneClassification(primary_scene="unknown", confidence=0)
        
        try:
            # Get frame data
            if hasattr(frame, 'data'):
                frame = frame.data
            
            # Analyze color distribution
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Calculate average brightness
            brightness = hsv[:, :, 2].mean()
            
            # Calculate color dominance
            hue_hist = cv2.calcHist([hsv], [0], None, [180], [0, 180])
            dominant_hue = hue_hist.argmax()
            
            # Simple classification rules
            if brightness > 180:
                scene = "outdoor" if dominant_hue > 90 else "studio"
            elif brightness < 80:
                scene = "indoor"
            else:
                # Check for green (nature)
                if 35 < dominant_hue < 75:
                    scene = "nature"
                # Check for blue (sky/water)
                elif 90 < dominant_hue < 130:
                    scene = "outdoor"
                else:
                    scene = "indoor"
            
            return SceneClassification(
                primary_scene=scene,
                confidence=0.6,
                all_scenes={scene: 0.6}
            )
            
        except Exception as e:
            return SceneClassification(primary_scene="unknown", confidence=0)


# ==================== FACE ANALYZER ====================

class FaceAnalyzer:
    """
    Face detection and analysis
    """
    
    def __init__(self):
        self._cascade = None
        if HAS_CV2:
            try:
                self._cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                )
            except:
                pass
    
    def detect_faces(self, frame: Any) -> FaceDetection:
        """Detect faces in frame"""
        if not HAS_CV2 or self._cascade is None:
            return FaceDetection(face_count=0)
        
        try:
            if hasattr(frame, 'data'):
                frame = frame.data
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._cascade.detectMultiScale(gray, 1.1, 4)
            
            face_list = []
            for (x, y, w, h) in faces:
                face_list.append({
                    "bbox": (x, y, x+w, y+h),
                    "size": w * h
                })
            
            return FaceDetection(
                face_count=len(faces),
                faces=face_list
            )
            
        except Exception as e:
            return FaceDetection(face_count=0)
    
    async def analyze_video_faces(self, frames: List[Any]) -> FaceDetection:
        """Analyze faces across video"""
        total_faces = 0
        max_faces = 0
        all_faces = []
        
        for frame in frames:
            result = self.detect_faces(frame)
            total_faces += result.face_count
            max_faces = max(max_faces, result.face_count)
            all_faces.extend(result.faces)
        
        return FaceDetection(
            face_count=max_faces,  # Peak face count
            faces=all_faces[:10]  # Sample faces
        )


# ==================== OCR EXTRACTOR ====================

class OCRExtractor:
    """
    Text extraction from video frames
    """
    
    def __init__(self):
        self._reader = None
        self._initialized = False
    
    def _initialize(self):
        """Lazy load EasyOCR"""
        if self._initialized:
            return
        
        try:
            import easyocr
            self._reader = easyocr.Reader(['en', 'id'], gpu=False)
            print("[VISION] EasyOCR initialized")
        except ImportError:
            print("[VISION] EasyOCR not available")
        
        self._initialized = True
    
    def extract_text(self, frame: Any) -> OCRResult:
        """Extract text from frame"""
        self._initialize()
        
        if self._reader is None:
            return OCRResult(texts=[], confidences=[], locations=[])
        
        try:
            if hasattr(frame, 'data'):
                frame = frame.data
            
            results = self._reader.readtext(frame)
            
            texts = []
            confidences = []
            locations = []
            
            for (bbox, text, conf) in results:
                if conf > 0.5:  # Confidence threshold
                    texts.append(text)
                    confidences.append(conf)
                    # Convert bbox to simple format
                    x_coords = [p[0] for p in bbox]
                    y_coords = [p[1] for p in bbox]
                    locations.append((
                        int(min(x_coords)), int(min(y_coords)),
                        int(max(x_coords)), int(max(y_coords))
                    ))
            
            return OCRResult(
                texts=texts,
                confidences=confidences,
                locations=locations
            )
            
        except Exception as e:
            print(f"[VISION] OCR error: {e}")
            return OCRResult(texts=[], confidences=[], locations=[])


# ==================== MAIN VIDEO ANALYZER ====================

class VideoAnalyzer:
    """
    Complete video analysis pipeline
    """
    
    def __init__(self):
        self.object_detector = ObjectDetector()
        self.scene_classifier = SceneClassifier()
        self.face_analyzer = FaceAnalyzer()
        self.ocr = OCRExtractor()
    
    async def analyze_video(
        self,
        frames: List[Any],
        detect_objects: bool = True,
        classify_scenes: bool = True,
        detect_faces: bool = True,
        extract_text: bool = False,  # Expensive, off by default
        sample_rate: int = 5
    ) -> VisionResult:
        """Full video analysis"""
        start_time = datetime.now()
        
        result = VisionResult(
            video_path="",
            frame_count=len(frames)
        )
        
        # Sample frames for analysis
        sampled = frames[::sample_rate]
        
        # Object detection
        if detect_objects:
            result.objects = await self.object_detector.detect_video(sampled)
        
        # Scene classification (use first few frames)
        if classify_scenes and sampled:
            scenes = [self.scene_classifier.classify(f) for f in sampled[:5]]
            result.scenes = scenes
        
        # Face detection
        if detect_faces:
            result.faces = await self.face_analyzer.analyze_video_faces(sampled)
        
        # OCR (expensive, use sparingly)
        if extract_text and sampled:
            # Only first and last frame
            ocr_results = [self.ocr.extract_text(sampled[0])]
            if len(sampled) > 1:
                ocr_results.append(self.ocr.extract_text(sampled[-1]))
            
            all_texts = []
            all_conf = []
            all_loc = []
            for ocr in ocr_results:
                all_texts.extend(ocr.texts)
                all_conf.extend(ocr.confidences)
                all_loc.extend(ocr.locations)
            
            result.ocr = OCRResult(all_texts, all_conf, all_loc)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        result.processing_time_ms = processing_time
        
        return result
    
    def analyze_frame(self, frame: Any) -> Dict[str, Any]:
        """Quick single frame analysis"""
        return {
            "objects": self.object_detector.detect(frame),
            "scene": self.scene_classifier.classify(frame),
            "faces": self.face_analyzer.detect_faces(frame)
        }
