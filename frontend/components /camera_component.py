"""
Health Insights Agent - Camera Component (Cleaned Version)
Camera and document capture module with TrOCR integration
"""

import cv2
import os
import uuid
import asyncio
import sqlite3
import json
import logging
import shutil
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, List, Callable
from PIL import Image, ImageEnhance, ImageOps
import numpy as np
from pathlib import Path

# TrOCR imports
try:
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    import torch
    TROCR_AVAILABLE = True
except ImportError:
    TROCR_AVAILABLE = False
    print("Warning: TrOCR not available. Install with: pip install transformers torch")


class DocumentType(Enum):
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report" 
    MEDICAL_NOTE = "medical_note"
    INSURANCE_CARD = "insurance_card"
    OTHER = "other"


@dataclass
class CapturedDocument:
    """Main data structure for captured documents"""
    id: str
    file_path: str
    document_type: DocumentType
    capture_date: datetime
    file_size: int
    image_width: int
    image_height: int
    is_processed: bool = False
    ocr_text: Optional[str] = None
    confidence_score: Optional[float] = None
    tags: Optional[List[str]] = None
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['document_type'] = self.document_type.value
        data['capture_date'] = self.capture_date.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary"""
        data['document_type'] = DocumentType(data['document_type'])
        data['capture_date'] = datetime.fromisoformat(data['capture_date'])
        return cls(**data)


@dataclass 
class CameraConfig:
    """Configuration settings for camera component"""
    save_directory: str = "./documents"
    max_image_size: tuple = (1920, 1080)
    image_format: str = "PNG"
    compression_quality: int = 85
    auto_enhance: bool = True
    create_backup: bool = True


# Custom Exceptions
class CameraError(Exception):
    """Base exception for camera operations"""
    pass


class CameraNotAvailableError(CameraError):
    """Camera hardware not accessible"""
    pass


class StorageError(CameraError):
    """File storage/retrieval issues"""
    pass


class ImageProcessingError(CameraError):
    """Image processing failures"""
    pass


class DocumentStorage:
    """Handles document storage and database operations"""
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True, mode=0o700)  # Secure permissions
        self.db_path = self.storage_path / "documents.db"
        self.audit_logger = self._setup_audit_logger()
        self._init_database()
    
    def _setup_audit_logger(self):
        """Setup audit logging for compliance"""
        logger = logging.getLogger('document_audit')
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers to prevent duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        log_file = self.storage_path / 'audit.log'
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Secure log file permissions
        if log_file.exists():
            os.chmod(log_file, 0o600)
        
        return logger
    
    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                document_type TEXT NOT NULL,
                capture_date TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                image_width INTEGER NOT NULL,
                image_height INTEGER NOT NULL,
                is_processed BOOLEAN DEFAULT FALSE,
                ocr_text TEXT,
                confidence_score REAL,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Secure database permissions
        os.chmod(self.db_path, 0o600)
    
    def save_document(self, doc: CapturedDocument) -> bool:
        """Save document metadata to database with audit logging"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO documents 
                (id, file_path, document_type, capture_date, file_size, 
                 image_width, image_height, is_processed, ocr_text, 
                 confidence_score, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doc.id,
                doc.file_path,
                doc.document_type.value,
                doc.capture_date.isoformat(),
                doc.file_size,
                doc.image_width,
                doc.image_height,
                doc.is_processed,
                doc.ocr_text,
                doc.confidence_score,
                json.dumps(doc.tags) if doc.tags else None
            ))
            
            conn.commit()
            conn.close()
            
            # Audit logging
            self.audit_logger.info(f"Document saved: {doc.id} ({doc.document_type.value})")
            return True
            
        except Exception as e:
            self.audit_logger.error(f"Failed to save document {doc.id}: {e}")
            raise StorageError(f"Failed to save document: {e}")
    
    def get_all_documents(self) -> List[CapturedDocument]:
        """Retrieve all documents from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM documents ORDER BY capture_date DESC')
            rows = cursor.fetchall()
            conn.close()
            
            documents = []
            for row in rows:
                doc = CapturedDocument(
                    id=row[0],
                    file_path=row[1],
                    document_type=DocumentType(row[2]),
                    capture_date=datetime.fromisoformat(row[3]),
                    file_size=row[4],
                    image_width=row[5],
                    image_height=row[6],
                    is_processed=bool(row[7]),
                    ocr_text=row[8],
                    confidence_score=row[9],
                    tags=json.loads(row[10]) if row[10] else None
                )
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            raise StorageError(f"Failed to retrieve documents: {e}")
    
    def delete_document(self, document_id: str) -> bool:
        """Delete document from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM documents WHERE id = ?', (document_id,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            if deleted:
                self.audit_logger.info(f"Document deleted: {document_id}")
            
            return deleted
            
        except Exception as e:
            self.audit_logger.error(f"Failed to delete document {document_id}: {e}")
            raise StorageError(f"Failed to delete document: {e}")


class ImageProcessor:
    """Handles image processing and TrOCR integration"""
    
    def __init__(self):
        """Initialize TrOCR models"""
        self.trocr_handwritten = None
        self.trocr_printed = None
        self.trocr_processor = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") if TROCR_AVAILABLE else None
        
        if TROCR_AVAILABLE:
            print(f"TrOCR will use device: {self.device}")
        else:
            print("TrOCR not available - OCR functionality disabled")
    
    def _load_trocr_model(self, model_name: str):
        """Load TrOCR model on demand"""
        if not TROCR_AVAILABLE:
            raise ImportError("TrOCR not available")
        
        try:
            print(f"Loading TrOCR model: {model_name}")
            processor = TrOCRProcessor.from_pretrained(model_name)
            model = VisionEncoderDecoderModel.from_pretrained(model_name)
            model.to(self.device)
            return processor, model
            
        except Exception as e:
            raise ImageProcessingError(f"Failed to load TrOCR model: {e}")
    
    def extract_text_with_trocr(self, image_path: str, doc_type: DocumentType) -> tuple[str, float]:
        """Extract text using TrOCR (optimized for medical documents)"""
        
        if not TROCR_AVAILABLE:
            return "", 0.0
        
        try:
            # Choose model based on document type
            if doc_type == DocumentType.PRESCRIPTION:
                # Prescriptions are often handwritten
                if not self.trocr_handwritten:
                    self.trocr_processor, self.trocr_handwritten = self._load_trocr_model(
                        'microsoft/trocr-base-handwritten'
                    )
                processor, model = self.trocr_processor, self.trocr_handwritten
            else:
                # Lab reports, insurance cards are usually printed
                if not self.trocr_printed:
                    self.trocr_processor, self.trocr_printed = self._load_trocr_model(
                        'microsoft/trocr-base-printed'
                    )
                processor, model = self.trocr_processor, self.trocr_printed
            
            # Load and preprocess image
            image = Image.open(image_path).convert('RGB')
            pixel_values = processor(image, return_tensors="pt").pixel_values.to(self.device)
            
            # Generate text
            generated_ids = model.generate(pixel_values)
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # Estimate confidence score
            confidence = self._estimate_trocr_confidence(generated_text)
            
            return generated_text.strip(), confidence
            
        except Exception as e:
            print(f"TrOCR processing failed: {e}")
            raise ImageProcessingError(f"TrOCR processing failed: {e}")
    
    def _estimate_trocr_confidence(self, text: str) -> float:
        """Estimate confidence for TrOCR output"""
        if not text or len(text) < 3:
            return 0.0
        
        confidence = 0.8  # Base confidence for TrOCR
        
        # Adjust based on text characteristics
        if len(text) > 50:
            confidence += 0.1
        
        # Check for medical terms
        medical_terms = ['mg', 'prescription', 'patient', 'doctor', 'medicine', 'dose', 'lab', 'result']
        if any(term.lower() in text.lower() for term in medical_terms):
            confidence += 0.1
        
        # Check for obvious errors
        error_patterns = ['###', '???', '***']
        if any(pattern in text for pattern in error_patterns):
            confidence -= 0.3
        
        return min(confidence, 1.0)
    
    @staticmethod
    def enhance_for_ocr(image_path: str, output_path: str) -> str:
        """Optimize image for OCR processing"""
        try:
            image = Image.open(image_path)
            
            # Convert to RGB for consistency
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Save optimized image
            image.save(output_path, optimize=True, quality=95)
            return output_path
            
        except Exception as e:
            raise ImageProcessingError(f"Failed to process image: {e}")
    
    @staticmethod
    def resize_image(image_path: str, max_size: tuple) -> str:
        """Resize image if too large"""
        try:
            image = Image.open(image_path)
            
            if image.size[0] <= max_size[0] and image.size[1] <= max_size[1]:
                return image_path
            
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            image.save(image_path, optimize=True)
            return image_path
            
        except Exception as e:
            raise ImageProcessingError(f"Failed to resize image: {e}")
    
    @staticmethod
    def strip_metadata(image_path: str) -> str:
        """Remove EXIF and metadata for privacy"""
        try:
            image = Image.open(image_path)
            
            # Create clean image without EXIF
            clean_image = Image.new(image.mode, image.size)
            clean_image.putdata(list(image.getdata()))
            
            # Save without metadata
            clean_image.save(image_path)
            os.chmod(image_path, 0o600)  # Secure file permissions
            return image_path
            
        except Exception as e:
            raise ImageProcessingError(f"Failed to strip metadata: {e}")
    
    @staticmethod
    def validate_file_safety(file_path: str) -> bool:
        """Validate file is safe image"""
        try:
            # Check file size (50MB limit)
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:
                return False
            
            # Check file signature
            with open(file_path, 'rb') as f:
                header = f.read(10)
            
            image_signatures = [
                b'\xFF\xD8\xFF',  # JPEG
                b'\x89PNG\r\n\x1a\n',  # PNG
                b'GIF87a', b'GIF89a',  # GIF
                b'RIFF',  # TIFF
            ]
            
            if not any(header.startswith(sig) for sig in image_signatures):
                return False
            
            # PIL validation
            with Image.open(file_path) as img:
                img.verify()
            return True
        except:
            return False


class DocumentCamera:
    """Main camera component for document capture with TrOCR integration"""
    
    def __init__(self, config: CameraConfig):
        self.config = self._validate_config(config)
        self.storage = DocumentStorage(config.save_directory)
        self.image_processor = ImageProcessor()
        self.progress_callback: Optional[Callable] = None
        self._camera = None
        
        # Ensure directories exist with secure permissions
        Path(config.save_directory).mkdir(exist_ok=True, mode=0o700)
        Path(config.save_directory, "processed").mkdir(exist_ok=True, mode=0o700)
        
        print(f"DocumentCamera initialized. Storage: {config.save_directory}")
    
    def _validate_config(self, config: CameraConfig) -> CameraConfig:
        """Validate configuration settings"""
        save_dir = Path(config.save_directory)
        if not save_dir.exists():
            save_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        valid_formats = ['PNG', 'JPEG', 'JPG', 'TIFF']
        if config.image_format.upper() not in valid_formats:
            raise ValueError(f"Invalid image format: {config.image_format}")
        
        if config.max_image_size:
            w, h = config.max_image_size
            if w < 100 or h < 100:
                raise ValueError("Image size too small")
        
        return config
    
    def _initialize_camera(self):
        """Initialize camera with retry logic"""
        if self._camera is None:
            for camera_index in range(3):  # Try different camera indices
                try:
                    self._camera = cv2.VideoCapture(camera_index)
                    if self._camera.isOpened():
                        print(f"Camera initialized (index: {camera_index})")
                        return
                except:
                    pass
                
                if self._camera:
                    self._camera.release()
                    self._camera = None
            
            raise CameraNotAvailableError("No camera available")
    
    def _generate_document_id(self) -> str:
        """Generate unique document ID"""
        return str(uuid.uuid4())
    
    def _call_progress(self, message: str, progress: float):
        """Call progress callback if set"""
        if self.progress_callback:
            self.progress_callback(message, progress)
    
    def _secure_delete(self, file_path: str):
        """Securely delete file"""
        if not os.path.exists(file_path):
            return
        
        try:
            file_size = os.path.getsize(file_path)
            
            # Overwrite with random data
            with open(file_path, 'r+b') as f:
                for _ in range(3):  # 3 passes
                    f.seek(0)
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            os.remove(file_path)
            
        except Exception:
            # Fallback to regular delete
            try:
                os.remove(file_path)
            except:
                pass
    
    async def capture_document(self, doc_type: DocumentType = DocumentType.OTHER) -> CapturedDocument:
        """Capture a new document photo with automatic OCR processing"""
        try:
            self._call_progress("Initializing camera...", 0.1)
            self._initialize_camera()
            
            self._call_progress("Capturing image...", 0.2)
            
            # Capture frame
            ret, frame = self._camera.read()
            if not ret:
                raise CameraError("Failed to capture image")
            
            # Generate unique filename
            doc_id = self._generate_document_id()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{doc_type.value}_{timestamp}_{doc_id[:8]}.{self.config.image_format.lower()}"
            file_path = Path(self.config.save_directory) / filename
            
            self._call_progress("Processing image...", 0.3)
            
            # Save original image
            cv2.imwrite(str(file_path), frame)
            
            # Get image dimensions
            height, width = frame.shape[:2]
            
            # Apply privacy protection
            self.image_processor.strip_metadata(str(file_path))
            
            # Resize if needed
            if self.config.max_image_size:
                self.image_processor.resize_image(str(file_path), self.config.max_image_size)
            
            self._call_progress("Extracting text with TrOCR...", 0.6)
            
            # Extract text with TrOCR
            ocr_text, confidence = self.image_processor.extract_text_with_trocr(str(file_path), doc_type)
            
            # Get final file size
            file_size = os.path.getsize(file_path)
            
            self._call_progress("Saving document...", 0.9)
            
            # Create document object with OCR results
            document = CapturedDocument(
                id=doc_id,
                file_path=str(file_path),
                document_type=doc_type,
                capture_date=datetime.now(),
                file_size=file_size,
                image_width=width,
                image_height=height,
                is_processed=True,  # Mark as processed since we did OCR
                ocr_text=ocr_text,
                confidence_score=confidence
            )
            
            # Save to database
            self.storage.save_document(document)
            
            self._call_progress("Complete!", 1.0)
            return document
            
        except Exception as e:
            if isinstance(e, CameraError):
                raise
            raise CameraError(f"Capture failed: {e}")
    
    async def import_from_file(self, file_path: str, doc_type: DocumentType) -> CapturedDocument:
        """Import existing image file with validation and OCR processing"""
        try:
            if not os.path.exists(file_path):
                raise StorageError(f"File not found: {file_path}")
            
            # Validate file safety
            if not self.image_processor.validate_file_safety(file_path):
                raise StorageError("Invalid or unsafe file type")
            
            self._call_progress("Reading file...", 0.1)
            
            # Read image to get dimensions
            image = cv2.imread(file_path)
            if image is None:
                raise ImageProcessingError("Invalid image file")
            
            height, width = image.shape[:2]
            
            # Generate new filename in our storage directory
            doc_id = self._generate_document_id()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{doc_type.value}_{timestamp}_{doc_id[:8]}.{self.config.image_format.lower()}"
            new_path = Path(self.config.save_directory) / filename
            
            self._call_progress("Copying and processing file...", 0.3)
            
            # Copy to our storage directory
            shutil.copy2(file_path, new_path)
            
            # Apply privacy protection
            self.image_processor.strip_metadata(str(new_path))
            
            # Resize if needed
            if self.config.max_image_size:
                self.image_processor.resize_image(str(new_path), self.config.max_image_size)
            
            self._call_progress("Extracting text with TrOCR...", 0.6)
            
            # Extract text with TrOCR
            ocr_text, confidence = self.image_processor.extract_text_with_trocr(str(new_path), doc_type)
            
            file_size = os.path.getsize(new_path)
            
            self._call_progress("Saving document...", 0.9)
            
            # Create document object with OCR results
            document = CapturedDocument(
                id=doc_id,
                file_path=str(new_path),
                document_type=doc_type,
                capture_date=datetime.now(),
                file_size=file_size,
                image_width=width,
                image_height=height,
                is_processed=True,  # Mark as processed since we did OCR
                ocr_text=ocr_text,
                confidence_score=confidence
            )
            
            # Save to database
            self.storage.save_document(document)
            
            self._call_progress("Complete!", 1.0)
            return document
            
        except Exception as e:
            if isinstance(e, (StorageError, ImageProcessingError)):
                raise
            raise StorageError(f"Import failed: {e}")
    
    def get_all_documents(self) -> List[CapturedDocument]:
        """Get list of all captured documents"""
        return self.storage.get_all_documents()
    
    def get_documents_by_type(self, doc_type: DocumentType) -> List[CapturedDocument]:
        """Filter documents by type"""
        all_docs = self.get_all_documents()
        return [doc for doc in all_docs if doc.document_type == doc_type]
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its file securely"""
        try:
            documents = self.get_all_documents()
            doc_to_delete = None
            
            for doc in documents:
                if doc.id == document_id:
                    doc_to_delete = doc
                    break
            
            if not doc_to_delete:
                return False
            
            # Secure delete file
            if os.path.exists(doc_to_delete.file_path):
                self._secure_delete(doc_to_delete.file_path)
            
            # Delete processed version if exists
            processed_path = self._get_processed_path(doc_to_delete.file_path)
            if os.path.exists(processed_path):
                self._secure_delete(processed_path)
            
            # Delete from database
            return self.storage.delete_document(document_id)
            
        except Exception as e:
            raise StorageError(f"Failed to delete document: {e}")
    
    def _get_processed_path(self, original_path: str) -> str:
        """Generate path for processed image"""
        path_obj = Path(original_path)
        processed_dir = path_obj.parent / "processed"
        processed_dir.mkdir(exist_ok=True, mode=0o700)
        
        stem = path_obj.stem + "_processed"
        return str(processed_dir / f"{stem}{path_obj.suffix}")
    
    def set_progress_callback(self, callback: Callable[[str, float], None]):
        """Set function to call during long operations"""
        self.progress_callback = callback
    
    def cleanup(self):
        """Release camera resources"""
        if self._camera is not None:
            self._camera.release()
            self._camera = None
            print("Camera resources released")
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.cleanup()


# Testing and example usage
async def test_enhanced_camera():
    """Test the enhanced camera component with TrOCR"""
    print("Testing Enhanced Medical Document Camera with TrOCR...")
    
    config = CameraConfig(
        save_directory="./medical_documents",
        max_image_size=(1920, 1080),
        auto_enhance=True
    )
    
    camera = DocumentCamera(config)
    
    def progress_callback(message: str, progress: float):
        print(f"Progress: {message} ({progress*100:.1f}%)")
    
    camera.set_progress_callback(progress_callback)
    
    try:
        # Test file import with TrOCR
        test_images = ["test_prescription.jpg", "test_image.jpg", "sample.png"]
        
        for test_image in test_images:
            if os.path.exists(test_image):
                print(f"\nTesting import: {test_image}")
                doc = await camera.import_from_file(test_image, DocumentType.PRESCRIPTION)
                print(f"Imported document: {doc.id}")
                print(f"OCR Text: {doc.ocr_text[:100]}..." if doc.ocr_text else "No text extracted")
                print(f"Confidence: {doc.confidence_score:.2f}" if doc.confidence_score else "N/A")
                break
        
        # Show all documents
        all_docs = camera.get_all_documents()
        print(f"\nTotal documents: {len(all_docs)}")
        
        for doc in all_docs[:5]:  # Show first 5
            print(f"- {doc.document_type.value}: {doc.id}")
            if doc.ocr_text:
                print(f"  Text: {doc.ocr_text[:50]}...")
            print(f"  Confidence: {doc.confidence_score:.2f}" if doc.confidence_score else "  No confidence score")
    
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        camera.cleanup()


if __name__ == "__main__":
    # Run enhanced test
    asyncio.run(test_enhanced_camera())