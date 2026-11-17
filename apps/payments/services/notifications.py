# apps/payments/services/notifications.py
import logging
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def notify_admin_review_needed(screenshot, problems=None):
    """
    Admin ko in-app notification bhejo.
    Email NAHI — database mein store karo, UI mein dikhega.
    """
    from apps.payments.models import AdminNotification

    problems = problems or []

    # ✅ User email use karo
    user_email = screenshot.uploaded_by.email
    user_name = getattr(screenshot.uploaded_by, 'display_name', '') or user_email

    # Priority decide karo
    severities = [p.get('severity', 'low') for p in problems]
    if 'critical' in severities:
        priority = 'critical'
    elif 'high' in severities:
        priority = 'high'
    elif 'medium' in severities:
        priority = 'medium'
    else:
        priority = 'low'

    # Title
    critical_count = sum(1 for p in problems if p.get('severity') == 'critical')
    high_count = sum(1 for p in problems if p.get('severity') == 'high')

    title = f"Review needed: Payment #{screenshot.id}"
    if critical_count or high_count:
        parts = []
        if critical_count:
            parts.append(f"{critical_count} critical")
        if high_count:
            parts.append(f"{high_count} high")
        title += f" ({', '.join(parts)})"

    # Message
    message = (
        f"User: {user_name}\n"
        f"Email: {user_email}\n"
        f"Amount: ₹{screenshot.amount}\n"
        f"UTR: {screenshot.transaction_id or 'N/A'}\n"
        f"Payment App: {screenshot.payment_app or 'N/A'}\n"
        f"Fraud Score: {screenshot.fraud_score}/100\n"
    )

    if problems:
        message += "\nProblems:\n"
        for p in problems:
            message += f"• [{p.get('severity', 'low').upper()}] {p.get('title', 'Issue')}\n"

    # Sab admins ko notification bhejo
    admins = User.objects.filter(is_staff=True, is_active=True)

    if not admins.exists():
        logger.warning(
            f"Koi admin nahi mila — payment #{screenshot.id} ka notification "
            f"kisi ko nahi gaya"
        )
        return []

    notifications = []
    for admin in admins:
        notif = AdminNotification.objects.create(
            type='review_needed',
            priority=priority,
            title=title,
            message=message,
            screenshot=screenshot,
            triggered_by=screenshot.uploaded_by,
            target_admin=admin,
            metadata={
                'problems': problems,
                'fraud_score': screenshot.fraud_score,
                'amount': str(screenshot.amount),
                'utr': screenshot.transaction_id,
                'tournament_id': screenshot.tournament_id,
                'registration_id': screenshot.registration_id,
            }
        )
        notifications.append(notif)

    logger.info(
        f"Admin notification created for payment #{screenshot.id} "
        f"— {len(notifications)} admins ko bheja"
    )
    return notifications


def mark_notification_actioned(screenshot, admin):
    """Jab admin accept/reject kare, notification actioned mark karo."""
    from apps.payments.models import AdminNotification

    AdminNotification.objects.filter(
        screenshot=screenshot,
        target_admin=admin,
        is_actioned=False
    ).update(
        is_actioned=True,
        is_read=True,
        read_at=timezone.now()
    )
    # ✅ admin.email use karo
    logger.info(f"Notification actioned for #{screenshot.id} by {admin.email}")


def notify_user_decision(screenshot, decision, notes=''):
    """User ko in-app notification bhejo jab admin decision le."""
    from apps.payments.models import UserNotification

    if decision == 'accepted':
        title = f"✅ Payment verified — #{screenshot.id}"
        message = (
            f"Aapka payment verify ho gaya hai!\n\n"
            f"Amount: ₹{screenshot.amount}\n"
            f"UTR: {screenshot.transaction_id or 'N/A'}\n"
            f"Tournament: {screenshot.tournament_id or 'N/A'}\n\n"
            f"Admin notes: {notes or 'Verified'}"
        )
    else:
        title = f"❌ Payment rejected — #{screenshot.id}"
        message = (
            f"Aapka payment reject kar diya gaya hai.\n\n"
            f"Amount: ₹{screenshot.amount}\n"
            f"UTR: {screenshot.transaction_id or 'N/A'}\n\n"
            f"Reason: {notes or 'No reason provided'}\n\n"
            f"Agar aapko lagta hai yeh galti hai, support se contact karein."
        )

    notif = UserNotification.objects.create(
        user=screenshot.uploaded_by,
        type='payment_decision',
        title=title,
        message=message,
        screenshot=screenshot,
    )

    # ✅ user.email use karo
    logger.info(
        f"User notification created for {screenshot.uploaded_by.email} "
        f"— {decision}"
    )
    return UserNotification