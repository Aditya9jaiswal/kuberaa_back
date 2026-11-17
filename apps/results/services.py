import re
import io
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class ResultOCRService:
    """Extract match result info from screenshot."""

    @staticmethod
    def extract_result_info(image_bytes):
        raw_text = ''
        confidence = 0.0

        try:
            import pytesseract
            from PIL import Image
            image = Image.open(io.BytesIO(image_bytes))
            raw_text = pytesseract.image_to_string(image)
            confidence = 0.85
        except ImportError:
            logger.warning("pytesseract not installed")
        except Exception as e:
            logger.exception(f"pytesseract failed: {e}")

        parsed = ResultOCRService._parse(raw_text)
        return {
            'success': bool(raw_text),
            'raw_text': raw_text,
            'confidence': confidence,
            'data': parsed,
        }

    @staticmethod
    def _parse(text):
        result = {
            'free_fire_uid': '',
            'player_name': '',
            'kills': 0,
            'placement': 0,
            'score': 0,
        }

        if not text:
            return result

        # FF UID — 8-12 digits
        uid = re.search(r'\b(\d{8,12})\b', text)
        if uid:
            result['free_fire_uid'] = uid.group(1)

        # Kills
        kills = re.search(r'(?:Kills?)[:\s]*(\d+)', text, re.I)
        if not kills:
            kills = re.search(r'(\d+)\s*Kills?', text, re.I)
        if kills:
            result['kills'] = int(kills.group(1))

        # Placement
        placement = re.search(r'(?:Placement|Rank|#)[:\s]*(\d+)', text, re.I)
        if placement:
            result['placement'] = int(placement.group(1))

        # Score
        score = re.search(r'(?:Score|Points)[:\s]*(\d+)', text, re.I)
        if score:
            result['score'] = int(score.group(1))

        # Name
        name = re.search(r'(?:Name|Player)[:\s]+([A-Z][a-zA-Z0-9_]{2,30})', text, re.I)
        if name:
            result['player_name'] = name.group(1).strip()

        # Auto-score = kills
        if result['score'] == 0 and result['kills'] > 0:
            result['score'] = result['kills']

        return result


class PrizeCalculationService:

    @staticmethod
    def calculate_prize(tournament, kills, placement):
        from .models import PrizeConfig

        try:
            config = PrizeConfig.objects.get(tournament=tournament, is_active=True)
        except PrizeConfig.DoesNotExist:
            return Decimal('0.00')

        prize = Decimal(str(kills)) * config.per_kill_amount

        if placement == 1:
            prize += config.first_place_bonus
        elif placement == 2:
            prize += config.second_place_bonus
        elif placement == 3:
            prize += config.third_place_bonus

        return prize