# apps/payments/utils/hashing.py
import hashlib
import io
import logging
from PIL import Image
import imagehash

logger = logging.getLogger(__name__)


def calculate_file_hash(file_obj):
    """
    SHA-256 hash of raw file bytes.
    Duplicate file detection ke liye.
    """
    sha256 = hashlib.sha256()
    
    # File object handle karo
    if hasattr(file_obj, 'chunks'):
        for chunk in file_obj.chunks():
            sha256.update(chunk)
        file_obj.seek(0)
    elif hasattr(file_obj, 'read'):
        for chunk in iter(lambda: file_obj.read(4096), b''):
            sha256.update(chunk)
        file_obj.seek(0)
    else:
        # Path hai
        with open(file_obj, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
    
    return sha256.hexdigest()


def calculate_perceptual_hash(file_path):
    """
    Perceptual hash — image ko crop/resize/edit karne par bhi
    same hash milega. Screenshot reuse detect karta hai.
    """
    try:
        img = Image.open(file_path)
        return str(imagehash.phash(img))
    except Exception as e:
        logger.exception(f"Perceptual hash failed: {e}")
        return ''


def calculate_hash_from_path(file_path):
    """SHA-256 hash from file path."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def calculate_perceptual_hash_from_bytes(image_bytes):
    """Perceptual hash from raw bytes."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return str(imagehash.phash(img))
    except Exception as e:
        logger.exception(f"Perceptual hash from bytes failed: {e}")
        return ''


def hamming_distance(hash1, hash2):
    """Do perceptual hashes ke beech difference (0-64)."""
    if not hash1 or not hash2:
        return 999
    if len(hash1) != len(hash2):
        return 999
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))