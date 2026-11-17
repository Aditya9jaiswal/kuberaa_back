from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Tournament, Registration
from core.firebase import FirestoreService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Tournament)
def sync_tournament_to_firestore(sender, instance, created, **kwargs):
    """Auto-sync tournament to Firestore."""
    try:
        fs = FirestoreService()
        data = {
            'id': str(instance.id),
            'title': instance.title,
            'description': instance.description,
            'rules': instance.rules,
            'prizeInfo': instance.prize_info,
            'tournamentDate': str(instance.tournament_date),
            'startTime': instance.start_time.isoformat(),
            'registrationStart': instance.registration_start.isoformat(),
            'registrationEnd': instance.registration_end.isoformat(),
            'maximumParticipants': instance.maximum_participants,
            'currentParticipants': instance.current_participants,
            'status': instance.status,
        }
        fs.create('tournaments', data, doc_id=str(instance.id))
        logger.info(f"Tournament {instance.title} synced")
    except Exception as e:
        logger.exception(f"Tournament sync failed: {e}")


@receiver(post_save, sender=Registration)
def sync_registration_to_firestore(sender, instance, created, **kwargs):
    """Auto-sync registration to Firestore."""
    try:
        fs = FirestoreService()
        data = {
            'id': str(instance.id),
            'tournamentId': str(instance.tournament.id),
            'userId': str(instance.user.id),
            'freeFireUid': instance.free_fire_uid,
            'freeFireName': instance.free_fire_name,
            'status': instance.status,
        }
        fs.create('registrations', data, doc_id=str(instance.id))
        logger.info(f"Registration synced for {instance.user.email}")
    except Exception as e:
        logger.exception(f"Registration sync failed: {e}")