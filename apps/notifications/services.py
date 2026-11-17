# apps/notifications/services.py

from apps.notifications.models import Notification
import logging

logger = logging.getLogger(__name__)


class NotificationService:

    # ═══════════════════════════════════════════════════════════
    # SOUND MAPPER — Notification type → Sound name
    # ═══════════════════════════════════════════════════════════
    SOUND_MAP = {
        # Payment
        'payment_submitted': 'payment',
        'payment_verified': 'payment',
        'payment_rejected': 'notification',

        # Tournament
        'tournament_registered': 'notification',
        'tournament_cancelled': 'notification',

        # Room / Match
        'room_released': 'room',      # ✅ room.mp3
        'room_revealed': 'room',      # ✅ room.mp3
        'match_start': 'room',        # ✅ room.mp3
        'can_play_approved': 'notification',

        # Result / Winning
        'result_published': 'result',  # ✅ result.mp3
        'winning': 'winning',          # ✅ winning.mp3
        'prize_paid': 'winning',       # ✅ winning.mp3

        # Admin
        'account_blocked': 'notification',
        'account_suspended': 'notification',
        'fraud_warning': 'notification',

        # Default
        'system': 'notification',
    }

    # ═══════════════════════════════════════════════════════════
    # CHANNEL MAPPER — Notification type → Android Channel (FIXED)
    # ═══════════════════════════════════════════════════════════
    CHANNEL_MAP = {
        'payment_submitted': 'payment_channel_v2',
        'payment_verified': 'payment_channel_v2',
        'payment_rejected': 'default_v2',

        'room_released': 'room_reveal_channel_v2',
        'room_revealed': 'room_reveal_channel_v2',
        'match_start': 'room_reveal_channel_v2',
        'can_play_approved': 'default_v2',

        'result_published': 'result_channel_v2',
        'winning': 'winning_channel_v2',
        'prize_paid': 'winning_channel_v2',

        'account_blocked': 'default_v2',
        'account_suspended': 'default_v2',
        'fraud_warning': 'default_v2',

        'tournament_registered': 'default_v2',
        'tournament_cancelled': 'default_v2',

        'default': 'default_v2',
    }

    # ═══════════════════════════════════════════════════════════
    # CORE — Create + Send FCM with Custom Sound
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def create_and_send(
        user,
        title,
        body,
        notification_type='system',
        tournament_id=None,
        match_id=None,
        data=None,
        send_push=True,
    ):
        """Create notification in DB + send FCM push with sound"""
        notification = Notification.objects.create(
            user=user,
            title=title,
            body=body,
            notification_type=notification_type,
            tournament_id=tournament_id,
            match_id=match_id,
            data=data or {},
        )

        # FCM push
        if send_push and getattr(user, 'fcm_token', None):
            try:
                NotificationService._send_fcm(
                    fcm_token=user.fcm_token,
                    title=title,
                    body=body,
                    notification_type=notification_type,
                    data={
                        'notification_id': str(notification.id),
                        'type': notification_type,
                        'title': title,
                        'body': body,
                        **(data or {}),
                    },
                )
            except Exception as e:
                logger.exception(f"FCM send failed: {e}")

        return notification

    # ═══════════════════════════════════════════════════════════
    # ✅ BACKWARD COMPATIBILITY METHOD (Jo error fix karega)
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def create_notification(user, title, message, notification_type='system', data=None):
        """
        ✅ FIXED: 'notification_type' accept karega (purane code ke liye)
        """
        try:
            return NotificationService.create_and_send(
                user=user,
                title=title,
                body=message,
                notification_type=notification_type,  # ✅ Sahi naam
                data=data or {},
            )
        except Exception as e:
            print(f"❌ create_notification error for {getattr(user, 'email', 'unknown')}: {e}")
            return None
    # ═══════════════════════════════════════════════════════════
    # FCM SENDER — with Custom Sound + Channel
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def _send_fcm(fcm_token, title, body, notification_type, data):
        """Send FCM push with custom sound + channel"""

        try:
            from firebase_admin import messaging

            # ✅ Sound decide karo
            sound_name = NotificationService.SOUND_MAP.get(
                notification_type, 'notification'
            )
            channel_id = NotificationService.CHANNEL_MAP.get(
                notification_type, 'default_v2'
            )

            logger.info(
                f'🔊 Sending FCM: type={notification_type}, '
                f'sound={sound_name}, channel={channel_id}'
            )

            message = messaging.Message(
                token=fcm_token,

                # ✅ Notification (app background mein dikhega)
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),

                # ✅ Data
                data={k: str(v) for k, v in data.items()},

                # ✅ Android — Custom sound + channel
                android=messaging.AndroidConfig(
                    priority='high',
                    ttl=3600,
                    notification=messaging.AndroidNotification(
                        title=title,
                        body=body,
                        sound=sound_name,       # ✅ Custom sound
                        channel_id=channel_id,  # ✅ Channel
                        priority='high',
                        default_sound=False,
                        default_vibrate_timings=True,
                        visibility='public',
                    ),
                ),

                # ✅ iOS — Custom sound
                apns=messaging.APNSConfig(
                    headers={
                        'apns-priority': '10',
                        'apns-push-type': 'alert',
                    },
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=title,
                                body=body,
                            ),
                            sound=f'{sound_name}.mp3',  # ✅ Custom sound
                            badge=1,
                            content_available=True,
                        ),
                    ),
                ),
            )

            response = messaging.send(message)
            logger.info(f"✅ FCM sent: {response}")
            return response

        except Exception as e:
            logger.exception(f"❌ FCM error: {e}")
            return None

    # ═══════════════════════════════════════════════════════════
    # PAYMENT
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def send_payment_submitted(user, tournament):
        return NotificationService.create_and_send(
            user=user,
            title='📤 Payment Submitted',
            body=(
                f'{tournament.title} ka payment submit ho gaya. '
                f'Admin verify karega.'
            ),
            notification_type='payment_submitted',
            tournament_id=tournament.id,
        )

    @staticmethod
    def send_payment_verified(user, tournament):
        return NotificationService.create_and_send(
            user=user,
            title='✅ Payment Verified!',
            body=(
                f'{tournament.title} ka payment approve ho gaya! '
                f'Match ke liye ready raho 🎮'
            ),
            notification_type='payment_verified',
            tournament_id=tournament.id,
        )

    @staticmethod
    def send_payment_rejected(user, tournament, reason=''):
        body = f'{tournament.title} ka payment reject ho gaya.'
        if reason:
            body += f'\nReason: {reason}'
        return NotificationService.create_and_send(
            user=user,
            title='❌ Payment Rejected',
            body=body,
            notification_type='payment_rejected',
            tournament_id=tournament.id,
        )

    # ═══════════════════════════════════════════════════════════
    # TOURNAMENT
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def send_tournament_registered(user, tournament):
        return NotificationService.create_and_send(
            user=user,
            title='🎮 Registration Confirmed',
            body=f'Aap {tournament.title} ke liye register ho gaye!',
            notification_type='tournament_registered',
            tournament_id=tournament.id,
        )

    @staticmethod
    def send_tournament_starting_soon(user, tournament, minutes_left):
        return NotificationService.create_and_send(
            user=user,
            title='⏰ Tournament Starting Soon',
            body=f'{tournament.title} {minutes_left} minute mein start hoga!',
            notification_type='match_start',
            tournament_id=tournament.id,
        )

    @staticmethod
    def send_tournament_cancelled(user, tournament, reason=''):
        body = f'{tournament.title} cancel ho gaya.'
        if reason:
            body += f'\nReason: {reason}'
        return NotificationService.create_and_send(
            user=user,
            title='❌ Tournament Cancelled',
            body=body,
            notification_type='tournament_cancelled',
            tournament_id=tournament.id,
        )

    # ═══════════════════════════════════════════════════════════
    # MATCH / ROOM
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def send_room_released(user, tournament, room_id=''):
        return NotificationService.create_and_send(
            user=user,
            title='🔓 Room Details Released!',
            body=(
                f'{tournament.title} ka room ID aur password aa gaya! '
                f'Abhi copy karo 🎮'
            ),
            notification_type='room_released',
            tournament_id=tournament.id,
            data={
                'room_id': room_id,
                'screen': 'match_room',
            },
        )

    @staticmethod
    def send_room_revealed(user, tournament, room_id=''):
        return NotificationService.create_and_send(
            user=user,
            title='🎮 Room Revealed!',
            body=(
                f'{tournament.title} ka room ab visible hai. '
                f'Match 5 min mein start hoga!'
            ),
            notification_type='room_revealed',
            tournament_id=tournament.id,
            data={
                'room_id': room_id,
                'screen': 'match_room',
            },
        )

    @staticmethod
    def send_match_start(user, tournament, minutes_left=5):
        return NotificationService.create_and_send(
            user=user,
            title='🎮 Match Starting Soon!',
            body=f'{tournament.title} ka match {minutes_left} min mein start hoga!',
            notification_type='match_start',
            tournament_id=tournament.id,
            data={'screen': 'match_room'},
        )

    @staticmethod
    def send_can_play_approved(user, tournament):
        return NotificationService.create_and_send(
            user=user,
            title='✅ You Can Play!',
            body=f'{tournament.title} mein aap khel sakte ho!',
            notification_type='can_play_approved',
            tournament_id=tournament.id,
        )

    # ═══════════════════════════════════════════════════════════
    # RESULTS
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def send_result_published(user, tournament):
        return NotificationService.create_and_send(
            user=user,
            title='🏆 Results Published!',
            body=f'{tournament.title} ka result aa gaya! Abhi dekho.',
            notification_type='result_published',
            tournament_id=tournament.id,
            data={'screen': 'result'},
        )

    @staticmethod
    def send_winning(user, tournament, prize_amount, kills=0, placement=0):
        body = f'Aapne {tournament.title} mein ₹{prize_amount} jeeta! 🎉'
        if kills or placement:
            body += f'\nKills: {kills} | Placement: #{placement}'
        return NotificationService.create_and_send(
            user=user,
            title='🏆 Congratulations!',
            body=body,
            notification_type='winning',
            tournament_id=tournament.id,
            data={
                'prize_amount': str(prize_amount),
                'kills': str(kills),
                'placement': str(placement),
                'screen': 'result',
            },
        )

    @staticmethod
    def send_prize_paid(user, tournament, amount):
        return NotificationService.create_and_send(
            user=user,
            title=f'💰 Prize Sent — ₹{amount}',
            body=f'Aapka ₹{amount} prize bhej diya gaya hai!',
            notification_type='prize_paid',
            tournament_id=tournament.id,
            data={
                'amount': str(amount),
                'screen': 'result',
            },
        )

    # ═══════════════════════════════════════════════════════════
    # ADMIN
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def send_account_blocked(user, reason=''):
        body = 'Aapka account block kar diya gaya hai.'
        if reason:
            body += f'\nReason: {reason}'
        return NotificationService.create_and_send(
            user=user,
            title='🚫 Account Blocked',
            body=body,
            notification_type='account_blocked',
        )

    @staticmethod
    def send_account_suspended(user, days=7, reason=''):
        body = f'Aapka account {days} din ke liye suspend hai.'
        if reason:
            body += f'\nReason: {reason}'
        return NotificationService.create_and_send(
            user=user,
            title='🚨 Account Suspended',
            body=body,
            notification_type='account_suspended',
        )

    @staticmethod
    def send_fraud_warning(user, warning_type, message):
        return NotificationService.create_and_send(
            user=user,
            title='⚠️ Fraud Warning',
            body=message,
            notification_type='fraud_warning',
            data={'fraud_type': warning_type},
        )

    # ═══════════════════════════════════════════════════════════
    # SYSTEM
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def send_welcome(user):
        return NotificationService.create_and_send(
            user=user,
            title='🎉 Welcome to Kuberaa',
            body='Tournaments join karo aur prizes jeeto!',
            notification_type='system',
        )

    @staticmethod
    def send_custom(user, title, body, notification_type='system', data=None):
        return NotificationService.create_and_send(
            user=user,
            title=title,
            body=body,
            notification_type=notification_type,
            data=data,
        )