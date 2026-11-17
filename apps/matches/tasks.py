from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Match, MatchParticipant          # ✅ MatchParticipant add
from apps.tournaments.models import Registration
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_room_releases():
    """Check matches whose room just released and send FCM."""
    now = timezone.now()

    matches = Match.objects.filter(
        room_release_time__lte=now,
        room_release_time__gte=now - timedelta(minutes=1),
        status=Match.Status.SCHEDULED,
    )

    for match in matches:
        # Sirf APPROVED participants ko bhejo
        participants = MatchParticipant.objects.filter(
            match=match,
            status=MatchParticipant.Status.APPROVED,
        ).select_related('user')

        for p in participants:
            try:
                from core.firebase import FCMService
                FCMService.send_to_user(
                    str(p.user.id),
                    f'Room Released - {match.display_name}',
                    'Room credentials available now! Join fast.',
                    {'match_id': str(match.id), 'type': 'room_released'},
                )
            except ImportError:
                logger.warning("FCM not configured")
            except Exception as e:
                logger.exception(f"FCM failed for {p.user_email}: {e}")

        match.status = Match.Status.ROOM_RELEASED
        match.save(update_fields=['status'])
        logger.info(f"Room released for match {match.match_number}")