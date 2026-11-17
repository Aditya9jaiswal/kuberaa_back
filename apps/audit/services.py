import logging
from core.firebase import FirestoreService

logger = logging.getLogger(__name__)


class AuditService:

    @staticmethod
    def log(admin_user, action, resource_type, resource_id, reason=''):
        try:
            fs = FirestoreService()
            fs.create('audit_logs', {
                'adminId': str(admin_user.id) if admin_user else None,
                'action': action,
                'resourceType': resource_type,
                'resourceId': str(resource_id),
                'reason': reason,
            })
        except Exception as e:
            logger.exception(f"Audit log failed: {e}")