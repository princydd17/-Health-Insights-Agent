"""
Health Insights Agent - Camera Component
Camera and document capture module for the hackathon project
"""

import cv2
import os
import uuid
import asyncio
import sqlite3
import hashlib
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, List, Callable
from PIL import Image, ImageEnhance, ImageOps
import numpy as np
from pathlib import Path


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
        self.storage_path.mkdir(exist_ok=True)
        self.db_path = self.storage_path / "documents.db"
        self._init_database()
    
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
    
    def save_document(self, doc: CapturedDocument) -> bool:
        """Save document metadata to database"""
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
            return True
            
        except Exception as e:
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
            
            return deleted
            
        except Exception as e:
            raise StorageError(f"Failed to delete document: {e}")


class ImageProcessor:
    """Handles image processing and optimization"""
    
    @staticmethod
    def enhance_for_ocr(image_path: str, output_path: str) -> str:
        """Optimize image for OCR processing"""
        try:
            # Open image with Pillow
            image = Image.open(image_path)
            
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Auto-adjust levels
            image = ImageOps.autocontrast(image)
            
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
            
            # Check if resize needed
            if image.size[0] <= max_size[0] and image.size[1] <= max_size[1]:
                return image_path
            
            # Calculate new size maintaining aspect ratio
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save resized image
            image.save(image_path, optimize=True)
            return image_path
            
        except Exception as e:
            raise ImageProcessingError(f"Failed to resize image: {e}")


class DocumentCamera:
    """Main camera component for document capture"""
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.storage = DocumentStorage(config.save_directory)
        self.image_processor = ImageProcessor()
        self.progress_callback: Optional[Callable] = None
        self._camera = None
        
        # Ensure directories exist
        Path(config.save_directory).mkdir(exist_ok=True)
        Path(config.save_directory, "processed").mkdir(exist_ok=True)
    
    def _initialize_camera(self):
        """Initialize camera if not already done"""
        if self._camera is None:
            self._camera = cv2.VideoCapture(0)
            if not self._camera.isOpened():
                raise CameraNotAvailableError("Cannot access camera")
    
    def _generate_document_id(self) -> str:
        """Generate unique document ID"""
        return str(uuid.uuid4())
    
    def _call_progress(self, message: str, progress: float):
        """Call progress callback if set"""
        if self.progress_callback:
            self.progress_callback(message, progress)
    
    async def capture_document(self, doc_type: DocumentType = DocumentType.OTHER) -> CapturedDocument:
        """Capture a new document photo"""
        try:
            self._call_progress("Initializing camera...", 0.1)
            self._initialize_camera()
            
            self._call_progress("Capturing image...", 0.3)
            
            # Capture frame
            ret, frame = self._camera.read()
            if not ret:
                raise CameraError("Failed to capture image")
            
            # Generate unique filename
            doc_id = self._generate_document_id()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{doc_type.value}_{timestamp}_{doc_id[:8]}.{self.config.image_format.lower()}"
            file_path = Path(self.config.save_directory) / filename
            
            self._call_progress("Processing image...", 0.5)
            
            # Save original image
            cv2.imwrite(str(file_path), frame)
            
            # Get image dimensions
            height, width = frame.shape[:2]
            
            # Resize if needed
            if self.config.max_image_size:
                self.image_processor.resize_image(str(file_path), self.config.max_image_size)
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            self._call_progress("Saving document...", 0.8)
            
            # Create document object
            document = CapturedDocument(
                id=doc_id,
                file_path=str(file_path),
                document_type=doc_type,
                capture_date=datetime.now(),
                file_size=file_size,
                image_width=width,
                image_height=height
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
        """Import existing image file"""
        try:
            if not os.path.exists(file_path):
                raise StorageError(f"File not found: {file_path}")
            
            self._call_progress("Reading file...", 0.2)
            
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
            
            self._call_progress("Copying file...", 0.5)
            
            # Copy to our storage directory
            import shutil
            shutil.copy2(file_path, new_path)
            
            # Resize if needed
            if self.config.max_image_size:
                self.image_processor.resize_image(str(new_path), self.config.max_image_size)
            
            file_size = os.path.getsize(new_path)
            
            self._call_progress("Saving document...", 0.8)
            
            # Create document object
            document = CapturedDocument(
                id=doc_id,
                file_path=str(new_path),
                document_type=doc_type,
                capture_date=datetime.now(),
                file_size=file_size,
                image_width=width,
                image_height=height
            )
            
            # Save to database
            self.storage.save_document(document)
            
            self._call_progress("Complete!", 1.0)
            return document
            
        except Exception as e:
            if isinstance(e, (StorageError, ImageProcessingError)):
                raise
            raise StorageError(f"Import failed: {e}")
    
    async def capture_multiple(self, count: int, doc_type: DocumentType) -> List[CapturedDocument]:
        """Capture multiple documents in sequence"""
        documents = []
        
        for i in range(count):
            self._call_progress(f"Capturing document {i+1}/{count}...", i/count)
            doc = await self.capture_document(doc_type)
            documents.append(doc)
            
            # Small delay between captures
            await asyncio.sleep(0.5)
        
        return documents
    
    def get_all_documents(self) -> List[CapturedDocument]:
        """Get list of all captured documents"""
        return self.storage.get_all_documents()
    
    def get_documents_by_type(self, doc_type: DocumentType) -> List[CapturedDocument]:
        """Filter documents by type"""
        all_docs = self.get_all_documents()
        return [doc for doc in all_docs if doc.document_type == doc_type]
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its file"""
        try:
            # Get document info first
            documents = self.get_all_documents()
            doc_to_delete = None
            
            for doc in documents:
                if doc.id == document_id:
                    doc_to_delete = doc
                    break
            
            if not doc_to_delete:
                return False
            
            # Delete file
            if os.path.exists(doc_to_delete.file_path):
                os.remove(doc_to_delete.file_path)
            
            # Delete processed version if exists
            processed_path = self._get_processed_path(doc_to_delete.file_path)
            if os.path.exists(processed_path):
                os.remove(processed_path)
            
            # Delete from database
            return self.storage.delete_document(document_id)
            
        except Exception as e:
            raise StorageError(f"Failed to delete document: {e}")
    
    def preprocess_for_ocr(self, document: CapturedDocument) -> str:
        """Return path to OCR-optimized version of image"""
        try:
            # Generate processed file path
            processed_path = self._get_processed_path(document.file_path)
            
            # Check if processed version already exists
            if os.path.exists(processed_path):
                return processed_path
            
            # Create processed version
            return self.image_processor.enhance_for_ocr(document.file_path, processed_path)
            
        except Exception as e:
            raise ImageProcessingError(f"Failed to preprocess image: {e}")
    
    def _get_processed_path(self, original_path: str) -> str:
        """Generate path for processed image"""
        path_obj = Path(original_path)
        processed_dir = path_obj.parent / "processed"
        processed_dir.mkdir(exist_ok=True)
        
        # Add _processed suffix
        stem = path_obj.stem + "_processed"
        return str(processed_dir / f"{stem}{path_obj.suffix}")
    
    def get_image_data(self, document: CapturedDocument) -> bytes:
        """Get raw image bytes for processing"""
        try:
            with open(document.file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            raise StorageError(f"Failed to read image data: {e}")
    
    def set_progress_callback(self, callback: Callable[[str, float], None]):
        """Set function to call during long operations"""
        self.progress_callback = callback
    
    def cleanup(self):
        """Release camera resources"""
        if self._camera is not None:
            self._camera.release()
            self._camera = None
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.cleanup()


# Example usage and testing
async def test_camera_component():
    """Test function to verify camera component works"""
    print("Testing Camera Component...")
    
    # Initialize camera with config
    config = CameraConfig(
        save_directory="./test_documents",
        max_image_size=(1280, 720),
        auto_enhance=True
    )
    
    camera = DocumentCamera(config)
    
    # Set progress callback
    def progress_callback(message: str, progress: float):
        print(f"Progress: {message} ({progress*100:.1f}%)")
    
    camera.set_progress_callback(progress_callback)
    
    try:
        # Test capture (you'll need a camera for this)
        print("\nTesting document capture...")
        # doc = await camera.capture_document(DocumentType.PRESCRIPTION)
        # print(f"Captured document: {doc.id}")
        
        # Test import from file (create a test image first)
        test_image_path = "test_image.jpg"
        if os.path.exists(test_image_path):
            print(f"\nTesting file import...")
            doc = await camera.import_from_file(test_image_path, DocumentType.LAB_REPORT)
            print(f"Imported document: {doc.id}")
            
            # Test OCR preprocessing
            processed_path = camera.preprocess_for_ocr(doc)
            print(f"Processed image saved to: {processed_path}")
        
        # Test getting all documents
        all_docs = camera.get_all_documents()
        print(f"\nTotal documents: {len(all_docs)}")
        
        for doc in all_docs:
            print(f"- {doc.document_type.value}: {doc.id} ({doc.file_size} bytes)")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        camera.cleanup()


if __name__ == "__main__":
    # Run test
    asyncio.run(test_camera_component())