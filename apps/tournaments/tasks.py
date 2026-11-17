# apps/tournaments/tasks.py

from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand


# ═══════════════════════════════════════════════════════════
# ✅ 5-MINUTE NOTIFICATION — Check karo har minute
# ═══════════════════════════════════════════════════════════

def send_room_reveal_notifications():
    """
    Ye function har 1 minute mein chalao (cron ya celery).
    Match start hone se 5 min pehle notification bhejta hai.
    """
    from apps.tournaments.models import Tournament, Registration
    from apps.notifications.services import NotificationService

    now = timezone.now()
    reveal_window_start = now
    reveal_window_end = now + timedelta(minutes=1)

    # Tournaments jo 5 min mein start honge
    upcoming = Tournament.objects.filter(
        start_time__gte=reveal_window_start,
        start_time__lte=reveal_window_end + timedelta(minutes=5),
    )

    for tournament in upcoming:
        # Check: 5 min ka window
        reveal_time = tournament.start_time - timedelta(minutes=5)

        if reveal_window_start <= reveal_time < reveal_window_end:
            # Notification bhejo
            regs = Registration.objects.filter(
                tournament=tournament,
                can_play=True,
            ).select_related('user')

            for reg in regs:
                try:
                    NotificationService.create_notification(
                        user=reg.user,
                        title='🎮 Room Revealed!',
                        message=(
                            f'{tournament.title} ka room ab visible hai!\n\n'
                            f'Match 5 min mein start hoga.\n'
                            f'Abhi room ID aur password dekho!'
                        ),
                        notification_type='room_revealed',
                    )
                    print(f'✅ Notification sent to {reg.user.email}')
                except Exception as e:
                    print(f'❌ Failed for {reg.user.email}: {e}')


# ═══════════════════════════════════════════════════════════
# MANAGEMENT COMMAND
# ═══════════════════════════════════════════════════════════

class Command(BaseCommand):
    help = 'Send room reveal notifications'

    def handle(self, *args, **options):
        send_room_reveal_notifications()