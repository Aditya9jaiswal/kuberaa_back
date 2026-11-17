# apps/payments/views.py

from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.authentication import JWTAuthentication

from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from core.responses import success_response, error_response
from apps.tournaments.models import Tournament

from apps.payments.models import (
    PaymentScreenshot,
    AdminReviewLog,
    AdminNotification,
    UserNotification,
    FraudLog,
)
from apps.payments.services.notifications import (
    mark_notification_actioned,
    notify_user_decision,
    notify_admin_review_needed,
)
from apps.payments.services.payment_verification import (
    PaymentVerificationService,
    DuplicateTransactionError,
    FraudDetectedError,
)

# ✅ Cache imports
from apps.results.cache_utils import (
    get_cached_notifications,
    set_cached_notifications,
    get_cached_unread_notifications,
    set_cached_unread_notifications,
    invalidate_notifications_cache,
)

import logging
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# BASE VIEWS
# ═══════════════════════════════════════════════════════════

class JWTAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class JWTAdminAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]


# ═══════════════════════════════════════════════════════════
# USER — UPI LINKS
# ═══════════════════════════════════════════════════════════

class UpiLinksView(JWTAPIView):
    def get(self, request, tournament_id):
        # ✅ Cache 10 min (rarely changes)
        cache_key = f'upi_links_{tournament_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return success_response(data=cached)

        try:
            t = Tournament.objects.get(id=tournament_id)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        upi_id = (t.upi_id or '').strip()
        upi_name = (t.upi_name or '').strip() or 'Kuberaa'
        amount = str(t.entry_fee or '0')

        if not upi_id:
            return error_response('Tournament UPI ID not set', 400)

        base = (
            f"upi://pay"
            f"?pa={upi_id}"
            f"&pn={upi_name}"
            f"&am={amount}"
            f"&cu=INR"
            f"&tn={t.title or 'Tournament'}"
        )

        data = {
            'upi_id': upi_id,
            'upi_name': upi_name,
            'amount': amount,
            'links': {
                'phonepe': base,
                'paytm': base,
            },
        }

        cache.set(cache_key, data, timeout=600)
        return success_response(data=data)


# ═══════════════════════════════════════════════════════════
# USER — OCR
# ═══════════════════════════════════════════════════════════

class ExtractUtrView(JWTAPIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image = request.FILES.get('screenshot') or request.FILES.get('image')

        if not image:
            return Response({
                'success': False,
                'error': {'message': 'Screenshot required'},
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            from apps.payments.services.ocr_service import OCRService
            image.seek(0)
            ocr_result = OCRService.extract_from_image(image)

            return Response({
                'success': True,
                'data': {
                    'transaction_id': ocr_result.get('transaction_id', ''),
                    'amount': str(ocr_result.get('amount', '0')),
                    'payment_date': str(ocr_result.get('payment_date', '')),
                    'payment_app': ocr_result.get('payment_app', ''),
                    'payer_upi_id': ocr_result.get('payer_upi_id', ''),
                    'confidence': ocr_result.get('confidence', 0),
                },
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"OCR error: {e}")
            return Response({
                'success': False,
                'error': {'message': f'OCR failed: {str(e)}'},
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════
# USER — SUBMIT PAYMENT
# ═══════════════════════════════════════════════════════════

class SubmitPaymentView(JWTAPIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image = request.FILES.get('image') or request.FILES.get('screenshot')

        utr = str(
            request.data.get('transaction_id', '')
            or request.data.get('utr', '')
            or request.data.get('manual_txn_id', '')
        ).strip().upper()

        tournament_id = request.data.get('tournament_id', '')
        registration_id = request.data.get('registration_id', '')
        amount = request.data.get('amount', 0)
        user_upi_id = request.data.get('user_upi_id', '')
        user_mobile = request.data.get('user_mobile', '')
        detected_app = request.data.get('detected_app', '')

        if not utr:
            return Response({
                'success': False,
                'error_type': 'MISSING_UTR',
                'message': 'UTR / Ref No required',
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(utr) < 8 or len(utr) > 25:
            return Response({
                'success': False,
                'error_type': 'INVALID_UTR',
                'message': 'UTR 8-25 characters ka hona chahiye',
            }, status=status.HTTP_400_BAD_REQUEST)

        if not utr.isalnum():
            return Response({
                'success': False,
                'error_type': 'INVALID_UTR',
                'message': 'UTR mein sirf letters aur numbers allowed hain',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = PaymentVerificationService.submit_payment(
                user=request.user,
                utr=utr,
                tournament_id=tournament_id,
                registration_id=registration_id,
                match_id=tournament_id,
                amount=amount,
                user_upi_id=user_upi_id,
                user_mobile=user_mobile,
                detected_app=detected_app,
                ip_address=self._get_client_ip(request),
            )

            if registration_id:
                try:
                    from apps.tournaments.models import Registration
                    reg = Registration.objects.filter(
                        id=registration_id,
                        user=request.user,
                    ).first()
                    if reg:
                        reg.status = 'PAYMENT_SUBMITTED'
                        reg.save(update_fields=['status'])
                except Exception as e:
                    logger.error(f"Registration update error: {e}")

            # ✅ NOTIFICATION — Payment submitted
            try:
                from apps.notifications.services import NotificationService
                if tournament_id:
                    tournament = Tournament.objects.filter(
                        id=tournament_id
                    ).first()
                    if tournament:
                        NotificationService.send_payment_submitted(
                            request.user, tournament,
                        )
                        # ✅ Cache invalidate
                        invalidate_notifications_cache(request.user.id)
            except Exception as e:
                logger.exception(f"Notification failed: {e}")

            return Response({
                'success': True,
                'message': result['message'],
                'data': {
                    'id': result['payment_id'],
                    'status': result['status'],
                    'fraud_score': result['fraud_score'],
                    'problems': result['problems'],
                },
            }, status=status.HTTP_201_CREATED)

        except DuplicateTransactionError as e:
            return Response({
                'success': False,
                'error_type': 'DUPLICATE_UTR',
                'message': str(e),
            }, status=status.HTTP_409_CONFLICT)

        except FraudDetectedError as e:
            return Response({
                'success': False,
                'error_type': 'FRAUD',
                'message': str(e),
            }, status=status.HTTP_403_FORBIDDEN)

        except Exception as e:
            logger.exception(f"Submit payment error: {e}")
            return Response({
                'success': False,
                'error': {'message': f'Submit failed: {str(e)}'},
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def _get_client_ip(request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# ═══════════════════════════════════════════════════════════
# USER — CHECK UTR
# ═══════════════════════════════════════════════════════════

class CheckUtrView(JWTAPIView):
    def post(self, request):
        utr = str(request.data.get('utr', '')).strip().upper()

        if not utr or len(utr) < 8 or len(utr) > 25:
            return Response({
                'success': False,
                'error': 'UTR 8-25 characters ka hona chahiye',
            }, status=status.HTTP_400_BAD_REQUEST)

        if not utr.isalnum():
            return Response({
                'success': False,
                'error': 'UTR mein sirf letters aur numbers allowed hain',
            }, status=status.HTTP_400_BAD_REQUEST)

        existing = PaymentScreenshot.objects.filter(
            transaction_id=utr
        ).exclude(uploaded_by=request.user).exists()

        if existing:
            return Response({
                'success': True,
                'data': {
                    'is_duplicate': True,
                    'message': 'Yeh UTR already use ho chuka hai',
                },
            })

        return Response({
            'success': True,
            'data': {
                'is_duplicate': False,
                'message': 'UTR available hai',
            },
        })


# ═══════════════════════════════════════════════════════════
# USER — FRAUD STATUS
# ═══════════════════════════════════════════════════════════

class FraudStatusView(JWTAPIView):
    def get(self, request):
        user = request.user
        recent = FraudLog.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=30),
        ).count()

        latest_log = FraudLog.objects.filter(
            user=user
        ).order_by('-created_at').first()

        return Response({
            'success': True,
            'data': {
                'account_status': getattr(user, 'status', 'ACTIVE'),
                'recent_fraud_attempts': recent,
                'fraud_type': latest_log.reason if latest_log else None,
                'warning_message': (
                    'Aapke account pe fraud warning hai.'
                    if recent >= 1 else None
                ),
            },
        })


# ═══════════════════════════════════════════════════════════
# USER — MY PAYMENTS
# ═══════════════════════════════════════════════════════════

class MyUploadsView(JWTAPIView):
    def get(self, request):
        # ✅ Cache 2 min
        cache_key = f'my_uploads_{request.user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        payments = PaymentScreenshot.objects.filter(
            uploaded_by=request.user
        ).order_by('-uploaded_at')[:50]

        response_data = {
            'success': True,
            'count': len(payments),
            'results': [{
                'id': p.id,
                'status': p.status,
                'transaction_id': p.transaction_id,
                'amount': str(p.amount),
                'uploaded_at': p.uploaded_at.isoformat(),
                'rejection_reason': p.rejection_reason,
                'admin_notes': p.admin_notes,
            } for p in payments],
        }

        cache.set(cache_key, response_data, timeout=120)
        return Response(response_data)


# ═══════════════════════════════════════════════════════════
# ADMIN — REVIEW QUEUE
# ═══════════════════════════════════════════════════════════

class AdminReviewQueueView(JWTAdminAPIView):
    def get(self, request):
        status_filter = request.query_params.get('status', 'manual_review')
        tournament_id = request.query_params.get('tournament_id', '')

        # ✅ Cache 1 min
        cache_key = f'admin_review_queue_{status_filter}_{tournament_id or "all"}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = PaymentScreenshot.objects.filter(status=status_filter)
        if tournament_id:
            qs = qs.filter(tournament_id=tournament_id)

        qs = qs.order_by('-uploaded_at')

        data = [{
            'id': p.id,
            'user_email': p.uploaded_by.email,
            'user_name': getattr(p.uploaded_by, 'display_name', '') or p.uploaded_by.email,
            'user_mobile': p.user_mobile,
            'user_upi_id': p.user_upi_id,
            'transaction_id': p.transaction_id,
            'amount': str(p.amount),
            'payment_app': p.payment_app,
            'tournament_id': p.tournament_id,
            'registration_id': p.registration_id,
            'status': p.status,
            'uploaded_at': p.uploaded_at.isoformat(),
        } for p in qs]

        response_data = {
            'success': True,
            'count': len(data),
            'results': data,
        }

        cache.set(cache_key, response_data, timeout=60)
        return Response(response_data)


# ═══════════════════════════════════════════════════════════
# ADMIN — REVIEW DECISION
# ═══════════════════════════════════════════════════════════

class AdminReviewDecisionView(JWTAdminAPIView):
    @transaction.atomic
    def post(self, request, pk):
        from apps.notifications.services import NotificationService

        p = get_object_or_404(
            PaymentScreenshot.objects.select_for_update(), pk=pk
        )

        decision = request.data.get('decision')
        notes = request.data.get('notes', '').strip()

        if decision not in ('accepted', 'rejected'):
            return Response(
                {'error': 'decision "accepted" ya "rejected" hona chahiye'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if decision == 'rejected' and not notes:
            return Response(
                {'error': 'Reject karne ke liye reason likhna zaroori hai'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        p.admin_decision = decision
        p.admin_reviewed_by = request.user
        p.admin_reviewed_at = timezone.now()
        p.admin_notes = notes

        if decision == 'accepted':
            p.status = 'verified'
            p.rejection_reason = ''
            if p.registration_id:
                try:
                    from apps.tournaments.models import Registration
                    reg = Registration.objects.filter(id=p.registration_id).first()
                    if reg:
                        reg.status = 'CONFIRMED'
                        reg.can_play = True
                        reg.save(update_fields=['status', 'can_play'])
                except Exception as e:
                    logger.error(f"Registration confirm error: {e}")
        else:
            p.status = 'rejected'
            p.rejection_reason = notes

        p.save()

        AdminReviewLog.objects.create(
            screenshot=p,
            admin=request.user,
            action=decision,
            notes=notes,
        )

        # ✅ NOTIFICATION + CACHE INVALIDATE
        try:
            mark_notification_actioned(p, request.user)
            notify_user_decision(p, decision, notes)

            # ✅ Cache invalidate
            invalidate_notifications_cache(p.uploaded_by.id)

            # ✅ Tournament-level notification
            if p.tournament:
                if decision == 'accepted':
                    NotificationService.send_payment_verified(
                        p.uploaded_by, p.tournament,
                    )
                else:
                    NotificationService.send_payment_rejected(
                        p.uploaded_by, p.tournament, reason=notes,
                    )
        except Exception as e:
            logger.warning(f"Notification failed: {e}")

        return Response({
            'success': True,
            'message': f'Payment {decision} kar diya gaya',
        })


# ═══════════════════════════════════════════════════════════
# ADMIN — NOTIFICATIONS
# ═══════════════════════════════════════════════════════════

class AdminNotificationListView(JWTAdminAPIView):
    def get(self, request):
        qs = AdminNotification.objects.filter(
            target_admin=request.user,
            is_actioned=False,
        ).order_by('-created_at')[:100]

        data = [{
            'id': n.id,
            'type': n.type,
            'priority': n.priority,
            'title': n.title,
            'message': n.message,
            'screenshot_id': n.screenshot_id,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        } for n in qs]

        return Response({
            'success': True,
            'count': len(data),
            'unread_count': AdminNotification.objects.filter(
                target_admin=request.user, is_read=False, is_actioned=False
            ).count(),
            'results': data,
        })


class AdminNotificationUnreadCountView(JWTAdminAPIView):
    def get(self, request):
        count = AdminNotification.objects.filter(
            target_admin=request.user,
            is_read=False,
            is_actioned=False,
        ).count()
        return Response({'success': True, 'unread_count': count})


class AdminNotificationReadView(JWTAdminAPIView):
    def post(self, request, pk):
        notif = get_object_or_404(
            AdminNotification, pk=pk, target_admin=request.user
        )
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save()
        return Response({'success': True})


class AdminNotificationReadAllView(JWTAdminAPIView):
    def post(self, request):
        AdminNotification.objects.filter(
            target_admin=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({'success': True})


# ═══════════════════════════════════════════════════════════
# USER — NOTIFICATIONS (CACHE)
# ═══════════════════════════════════════════════════════════

class UserNotificationListView(JWTAPIView):
    def get(self, request):
        user_id = request.user.id

        # ✅ Cache check
        cached = get_cached_notifications(user_id, filter_suffix='payments_all')
        cached_unread = get_cached_unread_notifications(user_id)

        if cached is not None:
            return Response({
                'success': True,
                'count': len(cached),
                'unread_count': cached_unread or 0,
                'results': cached,
            })

        # ✅ DB fetch
        qs = UserNotification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]

        data = [{
            'id': n.id,
            'type': n.type,
            'title': n.title,
            'message': n.message,
            'screenshot_id': n.screenshot_id,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        } for n in qs]

        unread_count = UserNotification.objects.filter(
            user=request.user, is_read=False
        ).count()

        # ✅ Cache 1 min
        set_cached_notifications(user_id, data, filter_suffix='payments_all', timeout=60)
        set_cached_unread_notifications(user_id, unread_count, timeout=60)

        return Response({
            'success': True,
            'count': len(data),
            'unread_count': unread_count,
            'results': data,
        })