import hashlib
import uuid
import logging
from typing import Optional

from .client import get_storage_bucket

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        self.bucket = get_storage_bucket()

    def upload_file(self, file_bytes: bytes, destination_path: str,
                    content_type: str = 'image/jpeg',
                    metadata: Optional[dict] = None) -> dict:
        blob = self.bucket.blob(destination_path)
        blob.content_type = content_type
        if metadata:
            blob.metadata = metadata
        blob.upload_from_string(file_bytes, content_type=content_type)
        blob.make_public()
        return {
            'storage_path': destination_path,
            'download_url': blob.public_url,
            'file_hash': hashlib.sha256(file_bytes).hexdigest(),
            'size': len(file_bytes),
            'content_type': content_type,
        }

    def generate_path(self, category: str, filename: str) -> str:
        ext = filename.split('.')[-1].lower() if '.' in filename else 'jpg'
        return f"{category}/{uuid.uuid4().hex}.{ext}"

    def delete_file(self, storage_path: str) -> None:
        blob = self.bucket.blob(storage_path)
        if blob.exists():
            blob.delete()