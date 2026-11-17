from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User
from core.firebase import FirestoreService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def sync_user_to_firestore(sender, instance, created, **kwargs):
    """Auto-sync user to Firestore on save."""
    try:
        fs = FirestoreService()
        data = {
            'id': str(instance.id),
            'email': instance.email,
            'displayName': instance.display_name,
            'mobileNumber': instance.mobile_number,
            'freeFireUid': instance.free_fire_uid,
            'freeFireName': instance.free_fire_name,
            'role': instance.role,
            'status': instance.status,
        }
        fs.create('users', data, doc_id=str(instance.id))
        logger.info(f"User {instance.email} synced to Firestore")
    except Exception as e:
        logger.exception(f"Firestore sync failed: {e}")