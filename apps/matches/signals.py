from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Match, MatchParticipant
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Match)
def sync_match_to_firestore(sender, instance, created, **kwargs):
    """Sync match to Firestore."""
    try:
        from core.firebase import FirestoreService
        fs = FirestoreService()
        data = {
            'id': str(instance.id),
            'tournamentId': str(instance.tournament.id),
            'matchNumber': instance.match_number,
            'scheduledStartTime': instance.scheduled_start_time.isoformat(),
            'roomReleaseTime': instance.room_release_time.isoformat(),
            'roomId': instance.room_id,
            'roomPassword': instance.room_password,
            'status': instance.status,
        }
        fs.create('matches', data, doc_id=str(instance.id))
    except ImportError:
        logger.warning("Firebase not configured, skipping sync")
    except Exception as e:
        logger.exception(f"Match sync failed: {e}")


@receiver(post_save, sender=MatchParticipant)
def on_participant_status_change(sender, instance, created, **kwargs):
    """Log participant status changes."""
    if created:
        logger.info(f"New participant: {instance.user_email} for Match {instance.match.match_number}")
    else:
        logger.info(f"Participant {instance.user_email} → {instance.status}")