# apps/notifications/views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from core.responses import success_response, error_response
from .models import Notification
from .tasks import send_bulk_notifications_task  # ✅ Worker Task import
from apps.users.models import User
from apps.results.cache_utils import (
    get_cached_notifications,
    set_cached_notifications,
    get_cached_unread_notifications,
    set_cached_unread_notifications,
    invalidate_notifications_cache,
)


# ═══════════════════════════════════════════════════════════
# LIST (cache-first)
# ═══════════════════════════════════════════════════════════
class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.user.id

        # Filters
        type_filter = request.query_params.get('type')
        unread_only = request.query_params.get('unread') == 'true'

        # ✅ Cache key — filters ke saath (taaki different filter different cache)
        cache_key_suffix = f"{type_filter or 'all'}_{'unread' if unread_only else 'all'}"

        # ✅ Cache check
        cached = get_cached_notifications(user_id, filter_suffix=cache_key_suffix)
        if cached is not None:
            return success_response(data=cached)

        # ✅ DB fetch
        qs = Notification.objects.filter(user=request.user).order_by('-created_at')

        if type_filter:
            qs = qs.filter(notification_type=type_filter)

        if unread_only:
            qs = qs.filter(is_read=False)

        data = []
        for n in qs:
            data.append({
                'id': str(n.id),
                'title': n.title,
                'message': n.body,
                'type': n.notification_type,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
                'expires_at': (
                    n.expires_at.isoformat() if n.expires_at else None
                ),
                'tournament_id': (
                    str(n.tournament_id) if n.tournament_id else None
                ),
                'match_id': (
                    str(n.match_id) if n.match_id else None
                ),
                'data': n.data if n.data else {},
                'link_type': (
                    n.data.get('screen') if n.data else None
                ),
            })

        # ✅ Cache 1 min
        set_cached_notifications(user_id, data, filter_suffix=cache_key_suffix, timeout=60)

        return success_response(data=data)


# ═══════════════════════════════════════════════════════════
# UNREAD COUNT (cache-first)
# ═══════════════════════════════════════════════════════════
class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.user.id

        # ✅ Cache check
        cached = get_cached_unread_notifications(user_id)
        if cached is not None:
            return success_response(data={'count': cached})

        # ✅ DB fetch
        count = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()

        # ✅ Cache 1 min
        set_cached_unread_notifications(user_id, count, timeout=60)

        return success_response(data={'count': count})


# ═══════════════════════════════════════════════════════════
# MARK ONE READ
# ═══════════════════════════════════════════════════════════
class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        try:
            n = Notification.objects.get(
                id=notification_id,
                user=request.user,
            )
        except Notification.DoesNotExist:
            return error_response('Not found', 404)

        if not n.is_read:
            n.is_read = True
            n.read_at = timezone.now()
            n.save(update_fields=['is_read', 'read_at'])

            # ✅ Cache invalidate
            invalidate_notifications_cache(request.user.id)

        return success_response(message='Marked as read')


# ═══════════════════════════════════════════════════════════
# MARK ALL READ
# ═══════════════════════════════════════════════════════════
class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )

        # ✅ Cache invalidate
        invalidate_notifications_cache(request.user.id)

        return success_response(
            message=f'{count} notifications marked as read'
        )


# ═══════════════════════════════════════════════════════════
# DELETE ONE
# ═══════════════════════════════════════════════════════════
class NotificationDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, notification_id):
        try:
            n = Notification.objects.get(
                id=notification_id,
                user=request.user,
            )
        except Notification.DoesNotExist:
            return error_response('Not found', 404)

        n.delete()

        # ✅ Cache invalidate
        invalidate_notifications_cache(request.user.id)

        return success_response(message='Notification deleted')


# ═══════════════════════════════════════════════════════════
# DELETE ALL
# ═══════════════════════════════════════════════════════════
class NotificationDeleteAllView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        count, _ = Notification.objects.filter(
            user=request.user,
        ).delete()

        # ✅ Cache invalidate
        invalidate_notifications_cache(request.user.id)

        return success_response(
            message=f'{count} notifications deleted'
        )


# ═══════════════════════════════════════════════════════════
# ✅ ADMIN BULK NOTIFICATION (Naya)
# ═══════════════════════════════════════════════════════════
class AdminSendNotificationView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        title = request.data.get('title')
        message = request.data.get('message')
        user_ids = request.data.get('user_ids', [])
        notif_type = request.data.get('type', 'system')

        if not title or not message:
            return error_response('Title and message required', 400)

        # Agar "all" bheja hai toh saare users utha lo
        if user_ids == "all":
            user_ids = list(User.objects.values_list('id', flat=True))
        # Agar single string hai toh list me convert karo
        elif isinstance(user_ids, str):
            user_ids = [user_ids]

        if not user_ids:
            return error_response('No users selected', 400)

        # ✅ Background Worker ko de diya (API turant response dega)
        send_bulk_notifications_task.delay(user_ids, title, message, notif_type)

        return success_response(
            message=f'Notification bhejna shuru ho gaya {len(user_ids)} users ko!'
        )