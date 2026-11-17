# apps/payments/services/image_forensics.py
import io
import logging
from PIL import Image, ImageChops
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)


class ImageForensics:
    """Image tampering detection — ELA + EXIF check."""
    
    EDITING_SOFTWARE = [
        'photoshop', 'gimp', 'paint', 'canva', 'pixlr',
        'snapseed', 'lightroom', 'affinity', 'picsart',
        'pixart', 'adobe', 'corel', 'inkscape',
    ]
    
    @classmethod
    def analyze(cls, image_file):
        """
        Complete image forensics.
        Returns dict with tampering indicators.
        """
        result = {
            'is_tampered': False,
            'has_editing_software': False,
            'ela_anomaly': False,
            'exif_suspicious': False,
            'details': {},
        }
        
        try:
            # Reset file pointer
            if hasattr(image_file, 'seek'):
                image_file.seek(0)
            
            img = Image.open(image_file)
            img.load()  # Force load
            
            # 1. EXIF check
            try:
                exif = cls._check_exif(img)
                result['details']['exif'] = exif
                if exif.get('editing_software'):
                    result['has_editing_software'] = True
                if exif.get('suspicious'):
                    result['exif_suspicious'] = True
            except Exception as e:
                logger.warning(f"EXIF check failed: {e}")
                result['details']['exif'] = {'error': str(e)}
            
            # 2. ELA (Error Level Analysis)
            try:
                ela_score = cls._ela_analysis(img)
                result['details']['ela_score'] = ela_score
                if ela_score > 0.7:
                    result['ela_anomaly'] = True
                    result['is_tampered'] = True
            except Exception as e:
                logger.warning(f"ELA failed: {e}")
                result['details']['ela_score'] = 0.0
            
            # 3. Metadata check
            if not result['details'].get('exif', {}).get('has_exif'):
                result['details']['no_exif'] = True
            
        except Exception as e:
            logger.exception(f"Forensics failed: {e}")
            result['details']['error'] = str(e)
        
        # Reset file pointer
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        
        return result
    
    @staticmethod
    def _check_exif(img):
        """EXIF metadata check."""
        result = {
            'has_exif': False,
            'editing_software': None,
            'suspicious': False,
        }
        
        try:
            exif_data = img.getexif()
            if exif_data:
                result['has_exif'] = True
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'Software':
                        software = str(value).lower()
                        for edit_sw in ImageForensics.EDITING_SOFTWARE:
                            if edit_sw in software:
                                result['editing_software'] = str(value)
                                result['suspicious'] = True
                                break
        except Exception as e:
            logger.warning(f"EXIF read failed: {e}")
        
        return result
    
    @staticmethod
    def _ela_analysis(img):
        """
        Error Level Analysis — edited regions mein
        compression level different hota hai.
        Returns anomaly score 0-1.
        """
        try:
            # Convert to RGB
            img = img.convert('RGB')
            
            # Save at 90% quality to temp buffer
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=90)
            buffer.seek(0)
            recompressed = Image.open(buffer)
            
            # Difference calculate karo
            diff = ImageChops.difference(img, recompressed)
            
            # Stats
            extrema = diff.getextrema()
            max_diff = max([e[1] for e in extrema])
            
            # Normalize 0-1
            score = min(max_diff / 255, 1.0)
            return score
        except Exception as e:
            logger.exception(f"ELA failed: {e}")
            return 0.0