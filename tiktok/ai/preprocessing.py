"""
Data Preprocessing Pipeline for TikTok AI
Video decoding, audio extraction, text cleaning, validation, batch processing
"""

import asyncio
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any, AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ==================== DATA CLASSES ====================

@dataclass
class Frame:
    """Single video frame"""
    index: int
    timestamp: float  # seconds
    data: Any  # numpy array when available
    width: int = 0
    height: int = 0


@dataclass
class VideoMetadata:
    """Video file metadata"""
    path: str
    duration: float  # seconds
    fps: float
    width: int
    height: int
    frame_count: int
    codec: str = ""
    file_size: int = 0
    hash: str = ""


@dataclass
class AudioData:
    """Extracted audio data"""
    path: str
    duration: float
    sample_rate: int
    channels: int
    data: Optional[Any] = None  # numpy array when available


@dataclass
class CleanedText:
    """Cleaned and normalized text"""
    original: str
    cleaned: str
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    emojis: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    language: str = "unknown"


@dataclass
class ValidationResult:
    """Data validation result"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality_score: float = 1.0  # 0-1


@dataclass
class BatchResult:
    """Batch processing result"""
    total: int
    successful: int
    failed: int
    results: List[Any] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)
    duration_seconds: float = 0.0


# ==================== VIDEO DECODER ====================

class VideoDecoder:
    """
    Video decoding and frame extraction
    Handles various formats and resolutions
    """
    
    SUPPORTED_FORMATS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    
    def __init__(self, target_resolution: int = 720):
        self.target_resolution = target_resolution
        
        if not HAS_CV2:
            print("[WARNING] OpenCV not installed. Video features limited.")
    
    async def get_metadata(self, video_path: str) -> VideoMetadata:
        """Extract video metadata"""
        path = Path(video_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        if not HAS_CV2:
            return VideoMetadata(
                path=video_path,
                duration=0, fps=0, width=0, height=0, frame_count=0,
                file_size=path.stat().st_size
            )
        
        cap = cv2.VideoCapture(video_path)
        
        try:
            metadata = VideoMetadata(
                path=video_path,
                duration=cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1),
                fps=cap.get(cv2.CAP_PROP_FPS),
                width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                codec=self._get_codec(cap),
                file_size=path.stat().st_size,
                hash=self._compute_hash(video_path)
            )
            return metadata
        finally:
            cap.release()
    
    async def extract_frames(
        self, 
        video_path: str, 
        fps: float = 1.0,
        max_frames: int = 100
    ) -> List[Frame]:
        """
        Extract frames from video at specified FPS
        
        Args:
            video_path: Path to video file
            fps: Frames per second to extract (1.0 = 1 frame per second)
            max_frames: Maximum frames to extract
        """
        if not HAS_CV2:
            print("[WARNING] OpenCV required for frame extraction")
            return []
        
        frames = []
        cap = cv2.VideoCapture(video_path)
        
        try:
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            frame_interval = int(video_fps / fps) if fps < video_fps else 1
            
            frame_index = 0
            extracted = 0
            
            while cap.isOpened() and extracted < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_index % frame_interval == 0:
                    # Resize if needed
                    if frame.shape[0] > self.target_resolution:
                        scale = self.target_resolution / frame.shape[0]
                        frame = cv2.resize(frame, None, fx=scale, fy=scale)
                    
                    frames.append(Frame(
                        index=extracted,
                        timestamp=frame_index / video_fps,
                        data=frame,
                        width=frame.shape[1],
                        height=frame.shape[0]
                    ))
                    extracted += 1
                
                frame_index += 1
            
            return frames
            
        finally:
            cap.release()
    
    async def extract_keyframes(self, video_path: str, threshold: float = 30.0) -> List[Frame]:
        """Extract keyframes based on scene change detection"""
        if not HAS_CV2:
            return []
        
        keyframes = []
        cap = cv2.VideoCapture(video_path)
        
        try:
            prev_frame = None
            frame_index = 0
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                if prev_frame is not None:
                    diff = cv2.absdiff(prev_frame, gray)
                    mean_diff = diff.mean()
                    
                    if mean_diff > threshold:
                        keyframes.append(Frame(
                            index=len(keyframes),
                            timestamp=frame_index / video_fps,
                            data=frame,
                            width=frame.shape[1],
                            height=frame.shape[0]
                        ))
                else:
                    # Always include first frame
                    keyframes.append(Frame(
                        index=0,
                        timestamp=0,
                        data=frame,
                        width=frame.shape[1],
                        height=frame.shape[0]
                    ))
                
                prev_frame = gray
                frame_index += 1
            
            return keyframes
            
        finally:
            cap.release()
    
    def _get_codec(self, cap) -> str:
        """Get video codec"""
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        return "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    
    def _compute_hash(self, video_path: str) -> str:
        """Compute file hash for caching"""
        hasher = hashlib.md5()
        with open(video_path, 'rb') as f:
            # Read first 1MB for quick hash
            hasher.update(f.read(1024 * 1024))
        return hasher.hexdigest()


# ==================== AUDIO EXTRACTOR ====================

class AudioExtractor:
    """
    Audio extraction and processing
    Supports speech-to-text preparation
    """
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
    
    async def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> AudioData:
        """Extract audio from video file"""
        if output_path is None:
            output_path = video_path.rsplit('.', 1)[0] + '.wav'
        
        # Use ffmpeg for extraction
        import subprocess
        
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',
            '-ar', str(self.sample_rate),
            '-ac', '1',  # Mono
            '-y',  # Overwrite
            output_path
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode == 0:
                return AudioData(
                    path=output_path,
                    duration=0,  # TODO: Calculate
                    sample_rate=self.sample_rate,
                    channels=1
                )
            else:
                raise RuntimeError(f"FFmpeg failed with code {process.returncode}")
                
        except FileNotFoundError:
            print("[WARNING] FFmpeg not found. Audio extraction unavailable.")
            return AudioData(path="", duration=0, sample_rate=0, channels=0)
    
    async def speech_to_text(self, audio_path: str) -> str:
        """Convert speech to text using Whisper"""
        try:
            import whisper
            
            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            return result["text"]
            
        except ImportError:
            print("[WARNING] Whisper not installed. Speech-to-text unavailable.")
            return ""


# ==================== TEXT CLEANER ====================

class TextCleaner:
    """
    Text cleaning and normalization
    Handles emojis, hashtags, mentions, URLs
    """
    
    # Regex patterns
    HASHTAG_PATTERN = re.compile(r'#(\w+)')
    MENTION_PATTERN = re.compile(r'@(\w+)')
    URL_PATTERN = re.compile(r'https?://\S+')
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", 
        flags=re.UNICODE
    )
    
    def __init__(self, max_emoji: int = 5, remove_urls: bool = True):
        self.max_emoji = max_emoji
        self.remove_urls = remove_urls
    
    def clean(self, text: str) -> CleanedText:
        """Clean and normalize text"""
        if not text:
            return CleanedText(original="", cleaned="")
        
        original = text
        
        # Extract components
        hashtags = self.HASHTAG_PATTERN.findall(text)
        mentions = self.MENTION_PATTERN.findall(text)
        urls = self.URL_PATTERN.findall(text)
        emojis = self.EMOJI_PATTERN.findall(text)
        
        # Clean text
        cleaned = text
        
        # Remove URLs
        if self.remove_urls:
            cleaned = self.URL_PATTERN.sub('', cleaned)
        
        # Limit emojis
        if len(emojis) > self.max_emoji:
            for emoji in emojis[self.max_emoji:]:
                cleaned = cleaned.replace(emoji, '', 1)
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Normalize hashtags (lowercase)
        for tag in hashtags:
            cleaned = cleaned.replace(f'#{tag}', f'#{tag.lower()}')
        
        return CleanedText(
            original=original,
            cleaned=cleaned.strip(),
            hashtags=[h.lower() for h in hashtags],
            mentions=mentions,
            emojis=emojis[:self.max_emoji],
            urls=urls,
            language=self._detect_language(cleaned)
        )
    
    def _detect_language(self, text: str) -> str:
        """Detect text language"""
        try:
            from langdetect import detect
            return detect(text)
        except:
            return "unknown"
    
    def normalize_hashtags(self, hashtags: List[str]) -> List[str]:
        """Normalize and deduplicate hashtags"""
        normalized = set()
        for tag in hashtags:
            # Remove #, lowercase
            clean_tag = tag.lstrip('#').lower()
            # Remove special chars
            clean_tag = re.sub(r'[^\w]', '', clean_tag)
            if clean_tag:
                normalized.add(clean_tag)
        return list(normalized)


# ==================== DATA VALIDATOR ====================

class DataValidator:
    """
    Data quality validation
    Ensures data meets requirements before AI processing
    """
    
    def __init__(self):
        self.min_text_length = 3
        self.max_text_length = 10000
        self.min_video_duration = 1.0  # seconds
        self.max_video_duration = 600.0  # 10 minutes
    
    def validate_text(self, text: str) -> ValidationResult:
        """Validate text data"""
        errors = []
        warnings = []
        
        if not text:
            errors.append("Text is empty")
            return ValidationResult(is_valid=False, errors=errors)
        
        if len(text) < self.min_text_length:
            errors.append(f"Text too short (min {self.min_text_length} chars)")
        
        if len(text) > self.max_text_length:
            warnings.append(f"Text very long, will be truncated")
        
        # Check for mostly emojis/symbols
        alpha_ratio = sum(c.isalpha() for c in text) / len(text)
        if alpha_ratio < 0.3:
            warnings.append("Text has low alphabetic content")
        
        quality_score = min(1.0, alpha_ratio + 0.3)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            quality_score=quality_score
        )
    
    def validate_video(self, metadata: VideoMetadata) -> ValidationResult:
        """Validate video metadata"""
        errors = []
        warnings = []
        
        if metadata.duration < self.min_video_duration:
            errors.append(f"Video too short (min {self.min_video_duration}s)")
        
        if metadata.duration > self.max_video_duration:
            warnings.append("Video very long, processing may be slow")
        
        if metadata.width < 320 or metadata.height < 240:
            warnings.append("Low resolution video")
        
        if metadata.fps < 15:
            warnings.append("Low frame rate")
        
        # Quality score based on resolution and duration
        resolution_score = min(1.0, (metadata.width * metadata.height) / (1920 * 1080))
        duration_score = 1.0 if self.min_video_duration <= metadata.duration <= 60 else 0.7
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            quality_score=(resolution_score + duration_score) / 2
        )
    
    def validate_profile(self, profile: Dict) -> ValidationResult:
        """Validate profile data for anomaly detection"""
        errors = []
        warnings = []
        
        required_fields = ['username', 'follower_count', 'following_count']
        for field in required_fields:
            if field not in profile:
                errors.append(f"Missing required field: {field}")
        
        if profile.get('follower_count', 0) < 0:
            errors.append("Invalid follower count")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


# ==================== BATCH PROCESSOR ====================

class BatchProcessor:
    """
    Batch processing for multiple items
    Supports parallel execution with resource limits
    """
    
    def __init__(
        self, 
        max_concurrent: int = 5,
        timeout_per_item: float = 30.0
    ):
        self.max_concurrent = max_concurrent
        self.timeout_per_item = timeout_per_item
    
    async def process_batch(
        self,
        items: List[Any],
        processor: Callable,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> BatchResult:
        """
        Process items in batch with concurrency limit
        
        Args:
            items: Items to process
            processor: Async function to process each item
            on_progress: Callback for progress updates (current, total)
        """
        start_time = datetime.now()
        results = []
        errors = []
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_limit(index: int, item: Any):
            async with semaphore:
                try:
                    result = await asyncio.wait_for(
                        processor(item),
                        timeout=self.timeout_per_item
                    )
                    return (index, result, None)
                except asyncio.TimeoutError:
                    return (index, None, "Timeout")
                except Exception as e:
                    return (index, None, str(e))
        
        # Create tasks
        tasks = [process_with_limit(i, item) for i, item in enumerate(items)]
        
        # Process with progress
        completed = 0
        for coro in asyncio.as_completed(tasks):
            index, result, error = await coro
            completed += 1
            
            if error:
                errors.append({"index": index, "error": error})
            else:
                results.append(result)
            
            if on_progress:
                on_progress(completed, len(items))
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return BatchResult(
            total=len(items),
            successful=len(results),
            failed=len(errors),
            results=results,
            errors=errors,
            duration_seconds=duration
        )
    
    async def process_stream(
        self,
        items: AsyncGenerator,
        processor: Callable,
        buffer_size: int = 10
    ) -> AsyncGenerator[Any, None]:
        """Process items from async generator with buffering"""
        buffer = []
        
        async for item in items:
            buffer.append(item)
            
            if len(buffer) >= buffer_size:
                batch_result = await self.process_batch(buffer, processor)
                for result in batch_result.results:
                    yield result
                buffer = []
        
        # Process remaining
        if buffer:
            batch_result = await self.process_batch(buffer, processor)
            for result in batch_result.results:
                yield result


# ==================== MAIN PIPELINE ====================

class PreprocessingPipeline:
    """
    Unified preprocessing pipeline
    Combines all preprocessing components
    """
    
    def __init__(self):
        self.video_decoder = VideoDecoder()
        self.audio_extractor = AudioExtractor()
        self.text_cleaner = TextCleaner()
        self.validator = DataValidator()
        self.batch_processor = BatchProcessor()
    
    async def preprocess_video(
        self, 
        video_path: str,
        extract_audio: bool = True,
        extract_frames: bool = True,
        fps: float = 1.0
    ) -> Dict[str, Any]:
        """Full video preprocessing"""
        result = {
            "video_path": video_path,
            "metadata": None,
            "frames": [],
            "audio": None,
            "validation": None
        }
        
        # Get metadata
        result["metadata"] = await self.video_decoder.get_metadata(video_path)
        
        # Validate
        result["validation"] = self.validator.validate_video(result["metadata"])
        
        if not result["validation"].is_valid:
            return result
        
        # Extract frames
        if extract_frames:
            result["frames"] = await self.video_decoder.extract_frames(video_path, fps=fps)
        
        # Extract audio
        if extract_audio:
            result["audio"] = await self.audio_extractor.extract_audio(video_path)
        
        return result
    
    def preprocess_text(self, text: str) -> Dict[str, Any]:
        """Full text preprocessing"""
        cleaned = self.text_cleaner.clean(text)
        validation = self.validator.validate_text(text)
        
        return {
            "original": text,
            "cleaned": cleaned,
            "validation": validation
        }
    
    async def preprocess_batch(
        self,
        items: List[Dict],
        item_type: str = "video"
    ) -> BatchResult:
        """Batch preprocessing"""
        if item_type == "video":
            processor = lambda x: self.preprocess_video(x["path"])
        else:
            processor = lambda x: asyncio.coroutine(lambda: self.preprocess_text(x["text"]))()
        
        return await self.batch_processor.process_batch(items, processor)
