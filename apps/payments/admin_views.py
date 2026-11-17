# apps/payments/admin_views.py
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from rest_framework.permissions import IsAdminUser, IsAuthenticated

from apps.payments.models import (
    PaymentScreenshot, AdminReviewLog, AdminNotification
)
from apps.payments.services.notifications import (
    mark_notification_actioned, notify_user_decision
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# REVIEW QUEUE
# ═══════════════════════════════════════════════════════════

class AdminReviewQueueView(APIView):
    """Admin ke liye pending review queue."""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        status_filter = request.query_params.get('status', 'manual_review')
        severity = request.query_params.get('severity', '')
        match_id = request.query_params.get('match_id', '')
        
        qs = PaymentScreenshot.objects.filter(status=status_filter)
        
        if match_id:
            qs = qs.filter(match_id=match_id)
        
        qs = qs.order_by('-fraud_score', '-uploaded_at')
        
        if severity:
            qs = [s for s in qs 
                  if any(p.get('severity') == severity for p in s.review_problems)]
        
        data = [{
            'id': s.id,
            'user': s.uploaded_by.username,
            'user_id': s.uploaded_by.id,
            'uploaded_at': s.uploaded_at.isoformat(),
            'match_id': s.match_id,
            'amount': str(s.amount),
            'transaction_id': s.transaction_id,
            'payment_app': s.payment_app,
            'fraud_score': s.fraud_score,
            'fraud_flags': s.fraud_flags,
            'problems': s.review_problems,
            'image_url': request.build_absolute_uri(s.image.url),
            'ocr_confidence': s.ocr_confidence,
            'user_history': {
                'total_uploads': PaymentScreenshot.objects.filter(
                    uploaded_by=s.uploaded_by).count(),
                'rejected': PaymentScreenshot.objects.filter(
                    uploaded_by=s.uploaded_by, status='rejected').count(),
                'verified': PaymentScreenshot.objects.filter(
                    uploaded_by=s.uploaded_by, status='verified').count(),
            }
        } for s in qs]
        
        return Response({
            'count': len(data),
            'results': data,
        })


class AdminReviewDetailView(APIView):
    """Ek screenshot ki poori detail — admin ke liye."""
    permission_classes = [IsAdminUser]
    
    def get(self, request, pk):
        s = get_object_or_404(PaymentScreenshot, pk=pk)
        
        return Response({
            'id': s.id,
            'user': {
                'id': s.uploaded_by.id,
                'username': s.uploaded_by.username,
                'email': s.uploaded_by.email,
                'date_joined': s.uploaded_by.date_joined.isoformat(),
            },
            'uploaded_at': s.uploaded_at.isoformat(),
            'ip_address': s.ip_address,
            'match_id': s.match_id,
            'ocr': {
                'confidence': s.ocr_confidence,
                'transaction_id': s.transaction_id,
                'amount': str(s.amount),
                'payer_name': s.payer_name,
                'payer_upi_id': s.payer_upi_id,
                'payment_date': s.payment_date.isoformat() if s.payment_date else None,
                'payment_time': s.payment_time.isoformat() if s.payment_time else None,
                'payment_app': s.payment_app,
                'raw_text': s.raw_text,
            },
            'fraud_score': s.fraud_score,
            'fraud_flags': s.fraud_flags,
            'problems': s.review_problems,
            'status': s.status,
            'image_url': request.build_absolute_uri(s.image.url),
            'file_hash': s.file_hash,
            'perceptual_hash': s.perceptual_hash,
            'user_history': {
                'total': PaymentScreenshot.objects.filter(
                    uploaded_by=s.uploaded_by).count(),
                'verified': PaymentScreenshot.objects.filter(
                    uploaded_by=s.uploaded_by, status='verified').count(),
                'rejected': PaymentScreenshot.objects.filter(
                    uploaded_by=s.uploaded_by, status='rejected').count(),
                'manual_review': PaymentScreenshot.objects.filter(
                    uploaded_by=s.uploaded_by, status='manual_review').count(),
            },
            'related_uploads': [{
                'id': r.id,
                'utr': r.transaction_id,
                'amount': str(r.amount),
                'status': r.status,
                'match_id': r.match_id,
                'uploaded_at': r.uploaded_at.isoformat(),
            } for r in PaymentScreenshot.objects.filter(
                uploaded_by=s.uploaded_by
            ).exclude(id=s.id).order_by('-uploaded_at')[:10]],
            'review_logs': [{
                'admin': log.admin.username,
                'action': log.action,
                'notes': log.notes,
                'at': log.created_at.isoformat(),
            } for log in s.review_logs.all()],
        })


class AdminReviewDecisionView(APIView):
    """Admin accept/reject kare."""
    permission_classes = [IsAdminUser]
    
    @transaction.atomic
    def post(self, request, pk):
        s = get_object_or_404(
            PaymentScreenshot.objects.select_for_update(), pk=pk
        )
        
        if s.status != 'manual_review':
            return Response(
                {'error': f'Yeh screenshot "{s.status}" state mein hai, '
                          f'review nahi ho sakta.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        decision = request.data.get('decision')
        notes = request.data.get('notes', '').strip()
        
        if decision not in ('accepted', 'rejected'):
            return Response(
                {'error': 'decision "accepted" ya "rejected" hona chahiye'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if decision == 'rejected' and not notes:
            return Response(
                {'error': 'Reject karne ke liye reason likhna zaroori hai'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update screenshot
        s.admin_decision = decision
        s.admin_reviewed_by = request.user
        s.admin_reviewed_at = timezone.now()
        s.admin_notes = notes
        
        if decision == 'accepted':
            s.status = 'verified'
            s.rejection_reason = ''
        else:
            s.status = 'rejected'
            s.rejection_reason = notes
        
        s.save()
        
        # Audit log
        AdminReviewLog.objects.create(
            screenshot=s,
            admin=request.user,
            action=decision,
            notes=notes,
        )
        
        # ⚠️ Notification actioned mark karo
        mark_notification_actioned(s, request.user)
        
        # ⚠️ User ko in-app notification bhejo
        notify_user_decision(s, decision, notes)
        
        return Response({
            'success': True,
            'message': f'Screenshot {decision} kar diya gaya',
            'screenshot': {
                'id': s.id,
                'status': s.status,
                'admin_decision': s.admin_decision,
                'admin_notes': s.admin_notes,
            }
        })


class AdminBulkDecisionView(APIView):
    """Ek saath multiple screenshots review karo."""
    permission_classes = [IsAdminUser]
    
    @transaction.atomic
    def post(self, request):
        ids = request.data.get('ids', [])
        decision = request.data.get('decision')
        notes = request.data.get('notes', '')
        
        if not ids or decision not in ('accepted', 'rejected'):
            return Response(
                {'error': 'ids aur valid decision chahiye'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated = 0
        for sid in ids:
            try:
                s = PaymentScreenshot.objects.select_for_update().get(
                    id=sid, status='manual_review'
                )
                s.admin_decision = decision
                s.admin_reviewed_by = request.user
                s.admin_reviewed_at = timezone.now()
                s.admin_notes = notes
                s.status = 'verified' if decision == 'accepted' else 'rejected'
                s.rejection_reason = notes if decision == 'rejected' else ''
                s.save()
                
                AdminReviewLog.objects.create(
                    screenshot=s, admin=request.user,
                    action=decision, notes=notes,
                )
                
                # Notification actioned + user notify
                mark_notification_actioned(s, request.user)
                notify_user_decision(s, decision, notes)
                
                updated += 1
            except PaymentScreenshot.DoesNotExist:
                continue
        
        return Response({
            'success': True,
            'updated': updated,
            'message': f'{updated} screenshots {decision}'
        })


# ═══════════════════════════════════════════════════════════
# ADMIN NOTIFICATIONS (In-App)
# ═══════════════════════════════════════════════════════════

class AdminNotificationListView(APIView):
    """Admin ke saare notifications."""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        unread_only = request.query_params.get('unread', 'false').lower() == 'true'
        priority = request.query_params.get('priority', '')
        notif_type = request.query_params.get('type', '')
        
        qs = AdminNotification.objects.filter(target_admin=request.user)
        
        if unread_only:
            qs = qs.filter(is_read=False)
        if priority:
            qs = qs.filter(priority=priority)
        if notif_type:
            qs = qs.filter(type=notif_type)
        
        qs = qs.filter(is_actioned=False)
        
        data = [{
            'id': n.id,
            'type': n.type,
            'priority': n.priority,
            'title': n.title,
            'message': n.message,
            'screenshot_id': n.screenshot_id,
            'triggered_by': n.triggered_by.username if n.triggered_by else None,
            'is_read': n.is_read,
            'metadata': n.metadata,
            'created_at': n.created_at.isoformat(),
        } for n in qs[:100]]
        
        return Response({
            'count': len(data),
            'unread_count': AdminNotification.objects.filter(
                target_admin=request.user, is_read=False, is_actioned=False
            ).count(),
            'results': data,
        })


class AdminNotificationUnreadCountView(APIView):
    """Sirf unread count — badge ke liye."""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        count = AdminNotification.objects.filter(
            target_admin=request.user,
            is_read=False,
            is_actioned=False
        ).count()
        return Response({'unread_count': count})


class AdminNotificationReadView(APIView):
    """Notification ko read mark karo."""
    permission_classes = [IsAdminUser]
    
    def post(self, request, pk):
        notif = get_object_or_404(
            AdminNotification, pk=pk, target_admin=request.user
        )
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save()
        return Response({'success': True})


class AdminNotificationReadAllView(APIView):
    """Saare notifications read mark karo."""
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        AdminNotification.objects.filter(
            target_admin=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({'success': True})


# ═══════════════════════════════════════════════════════════
# USER NOTIFICATIONS (In-App)
# ═══════════════════════════════════════════════════════════




class UserNotificationListView(APIView):
    permission_classes = [IsAuthenticated]   # ✅ Sahi
    
    def get(self, request):
        from apps.payments.models import UserNotification
        
        qs = UserNotification.objects.filter(user=request.user)
        
        data = [{
            'id': n.id,
            'type': n.type,
            'title': n.title,
            'message': n.message,
            'screenshot_id': n.screenshot_id,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        } for n in qs[:50]]
        
        return Response({
            'count': len(data),
            'unread_count': UserNotification.objects.filter(
                user=request.user, is_read=False
            ).count(),
            'results': data,
        })