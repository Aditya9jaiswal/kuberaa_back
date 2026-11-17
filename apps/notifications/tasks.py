# apps/notifications/tasks.py

from celery import shared_task
from firebase_admin import messaging
from apps.payments.models import UserNotification
from apps.users.models import User
from django.utils import timezone


@shared_task
def send_bulk_notifications_task(user_ids, title, message, notif_type='system'):
    """
    ⚡ BULK FCM Sender — 1000 users ko ek saath bhejta hai
    """
    print(f"🚀 Bulk notification started for {len(user_ids)} users...")
    start_time = timezone.now()

    # 1. Saare users fetch karo (sirf jinke paas fcm_token hai)
    users = User.objects.filter(id__in=user_ids).exclude(fcm_token__isnull=True).exclude(fcm_token='')
    
    if not users.exists():
        return "❌ No users with FCM token"

    # 2. DB Notifications bulk me create karo (fast)
    db_notifications = [
        UserNotification(
            user=user,
            type=notif_type,
            title=title,
            message=message,
        )
        for user in users
    ]
    UserNotification.objects.bulk_create(db_notifications)

    # 3. FCM Bulk Send — 500 tokens per batch (Google ki limit)
    tokens = [user.fcm_token for user in users]
    total_sent = 0
    total_failed = 0

    # Notification channels/sound decide karo
    sound_name = 'notification'
    channel_id = 'default_v2'
    
    if notif_type in ['winning', 'prize_paid']:
        sound_name = 'winning'
        channel_id = 'winning_channel_v2'
    elif notif_type == 'result_published':
        sound_name = 'result'
        channel_id = 'result_channel_v2'
    elif notif_type in ['room_released', 'room_revealed', 'match_start']:
        sound_name = 'room'
        channel_id = 'room_reveal_channel_v2'
    elif notif_type in ['payment_verified', 'payment_submitted']:
        sound_name = 'payment'
        channel_id = 'payment_channel_v2'

    # ✅ Batch me bhejo (500 at a time)
    batch_size = 500
    for i in range(0, len(tokens), batch_size):
        batch_tokens = tokens[i:i + batch_size]
        
        try:
            # ✅ Ek hi call me 500 users ko notification
            message_obj = messaging.MulticastMessage(
                tokens=batch_tokens,
                notification=messaging.Notification(
                    title=title,
                    body=message,
                ),
                data={'type': notif_type},
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        channel_id=channel_id,
                        sound=sound_name,
                    ),
                ),
            )
            
            response = messaging.send_each_for_multicast(message_obj)
            total_sent += response.success_count
            total_failed += response.failure_count
            
            print(f"✅ Batch {i//batch_size + 1}: {response.success_count} sent, {response.failure_count} failed")
            
        except Exception as e:
            print(f"❌ Batch error: {e}")
            total_failed += len(batch_tokens)

    elapsed = (timezone.now() - start_time).total_seconds()
    result_msg = f"✅ Sent: {total_sent}, Failed: {total_failed}, Time: {elapsed:.2f}s"
    print(result_msg)
    return result_msg