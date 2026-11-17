# apps/admin_panel/views.py

from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from firebase_admin import messaging
import logging
import json

from apps.users.models import User
from apps.tournaments.models import Tournament, Registration, PrizeConfig
from apps.matches.models import Match
from apps.payments.models import PaymentScreenshot, UserNotification
from apps.users.permissions import IsAdminRole
from apps.results.models import Result
from apps.notifications.tasks import send_bulk_notifications_task  # ✅ Naya Import

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# TOURNAMENTS
# ═══════════════════════════════════════════════════════════

class AdminTournamentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
    queryset = Tournament.objects.all().order_by('-created_at')

    def get_serializer_class(self):
        from apps.tournaments.serializers import TournamentSerializer
        return TournamentSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        status_filter = request.query_params.get('status')
        if status_filter and status_filter != 'ALL':
            queryset = queryset.filter(status=status_filter)

        type_filter = request.query_params.get('tournament_type')
        if type_filter and type_filter != 'ALL':
            queryset = queryset.filter(tournament_type=type_filter)

        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'data': serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request},
        )
        if serializer.is_valid():
            tournament = serializer.save()
            PrizeConfig.objects.get_or_create(tournament=tournament)

            return Response(
                {
                    'success': True,
                    'data': self.get_serializer(
                        tournament, context={'request': request}
                    ).data,
                    'message': f'Tournament #{tournament.display_id} created',
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        from apps.tournaments.serializers import TournamentSerializer
        data = TournamentSerializer(
            instance, context={'request': request}
        ).data

        matches = Match.objects.filter(
            tournament=instance
        ).order_by('match_number')

        data['matches'] = [
            {
                'id': str(m.id),
                'match_number': m.match_number,
                'title': getattr(m, 'title', ''),
                'room_id': getattr(m, 'room_id', ''),
                'room_password': getattr(m, 'room_password', ''),
                'scheduled_start_time': (
                    m.scheduled_start_time.isoformat()
                    if getattr(m, 'scheduled_start_time', None)
                    else None
                ),
                'status': m.status,
                'max_participants': getattr(m, 'max_participants', 0),
                'entry_fee': str(getattr(m, 'entry_fee', 0)),
                'payment_type': getattr(m, 'payment_type', 'CASH'),
                'points_required': getattr(m, 'points_required', 0),
            }
            for m in matches
        ]

        regs = Registration.objects.filter(
            tournament=instance
        ).select_related('user').order_by('-created_at')

        regs_data = []
        for r in regs:
            payment = PaymentScreenshot.objects.filter(
                uploaded_by=r.user,
                tournament_id=instance.id,
            ).order_by('-uploaded_at').first()

            utr = ''
            is_duplicate = False
            duplicate_info = ''
            screenshot_duplicate = False
            payment_app = ''

            if payment:
                utr = payment.transaction_id or ''
                payment_app = getattr(payment, 'payment_app', '') or ''

                if utr:
                    other = PaymentScreenshot.objects.filter(
                        transaction_id=utr
                    ).exclude(uploaded_by=r.user).first()
                    if other:
                        is_duplicate = True
                        duplicate_info = other.uploaded_by.email

            if payment and payment.image:
                image_name = str(payment.image.name)
                other_img = PaymentScreenshot.objects.filter(
                    image__endswith=image_name.split('/')[-1]
                ).exclude(id=payment.id).first()
                if other_img:
                    screenshot_duplicate = True

            regs_data.append({
                'id': str(r.id),
                'user_id': str(r.user.id),
                'user_name': getattr(r.user, 'display_name', '') or r.user.email,
                'user_email': r.user.email,
                'user_mobile': getattr(r, 'user_mobile', ''),
                'free_fire_uid': getattr(r, 'free_fire_uid', ''),
                'free_fire_name': getattr(r, 'free_fire_name', ''),
                'user_upi_id': getattr(r, 'user_upi_id', ''),
                'amount': str(instance.entry_fee),
                'entry_fee': str(instance.entry_fee),
                'status': r.status,
                'can_play': r.can_play,
                'transaction_id': utr,
                'utr': utr,
                'payment_app': payment_app,
                'is_duplicate': is_duplicate,
                'duplicate_info': duplicate_info,
                'screenshot_duplicate': screenshot_duplicate,
                'payment_id': str(payment.id) if payment else None,
                'payment_status': payment.status if payment else 'NO_PAYMENT',
                'created_at': (
                    r.created_at.isoformat() if r.created_at else None
                ),
            })

        data['registrations'] = regs_data
        data['total_registrations'] = len(regs_data)
        data['confirmed'] = regs.filter(
            status=Registration.Status.CONFIRMED
        ).count()
        data['confirmed_count'] = data['confirmed']
        data['pending_payment'] = regs.filter(
            status=Registration.Status.PENDING_PAYMENT
        ).count()
        data['payment_submitted'] = regs.filter(
            status=Registration.Status.PAYMENT_SUBMITTED
        ).count()

        room_data = None
        if hasattr(instance, 'match_room'):
            room = instance.match_room
            room_data = {
                'room_id': room.room_id,
                'room_password': room.room_password,
                'scheduled_at': (
                    str(room.scheduled_at) if room.scheduled_at else None
                ),
                'notes': room.notes,
            }
        data['match_room'] = room_data

        return Response({'success': True, 'data': data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
            context={'request': request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'Tournament updated',
            })
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        display_id = instance.display_id
        instance.delete()
        return Response(
            {'success': True, 'message': f'Tournament #{display_id} deleted'},
            status=status.HTTP_200_OK,
        )

# ═══════════════════════════════════════════════════════════
# REGISTRATIONS
# ═══════════════════════════════════════════════════════════

class AdminTournamentRegistrationsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, tournament_id):
        regs = Registration.objects.filter(
            tournament_id=tournament_id
        ).select_related('user').order_by('-created_at')

        data = []
        for r in regs:
            payment = PaymentScreenshot.objects.filter(
                uploaded_by=r.user,
                tournament_id=tournament_id,
            ).order_by('-uploaded_at').first()

            data.append({
                'id': str(r.id),
                'user_name': getattr(r.user, 'display_name', '') or r.user.email,
                'user_email': r.user.email,
                'user_mobile': getattr(r, 'user_mobile', ''),
                'free_fire_uid': getattr(r, 'free_fire_uid', ''),
                'free_fire_name': getattr(r, 'free_fire_name', ''),
                'user_upi_id': getattr(r, 'user_upi_id', ''),
                'amount': str(getattr(r, 'amount', 0)),
                'transaction_id': payment.transaction_id if payment else '',
                'payment_app': (
                    getattr(payment, 'payment_app', '') if payment else ''
                ),
                'status': getattr(r, 'status', 'PENDING_PAYMENT'),
                'can_play': getattr(r, 'can_play', False),
            })
        return Response({'success': True, 'data': data})

# ═══════════════════════════════════════════════════════════
# PRIZE CONFIG
# ═══════════════════════════════════════════════════════════

class AdminPrizeConfigView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, tournament_id):
        tournament = get_object_or_404(Tournament, id=tournament_id)
        config, _ = PrizeConfig.objects.update_or_create(
            tournament=tournament,
            defaults={
                'per_kill_amount': request.data.get('per_kill_amount', 0),
                'first_place_bonus': request.data.get('first_place_bonus', 0),
                'second_place_bonus': request.data.get('second_place_bonus', 0),
                'third_place_bonus': request.data.get('third_place_bonus', 0),
            },
        )
        return Response({'success': True, 'data': {'id': config.id}})

# ═══════════════════════════════════════════════════════════
# MATCHES
# ═══════════════════════════════════════════════════════════

class AdminMatchViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
    queryset = Match.objects.all().order_by('-created_at')

    def get_serializer_class(self):
        from apps.matches.serializers import MatchAdminSerializer
        return MatchAdminSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        tournament_id = request.query_params.get('tournament')
        if tournament_id:
            queryset = queryset.filter(tournament_id=tournament_id)

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'data': serializer.data})

    def create(self, request, *args, **kwargs):
        tournament_id = request.data.get('tournament')
        if tournament_id and not request.data.get('match_number'):
            from apps.tournaments.models import Tournament
            try:
                tournament = Tournament.objects.get(id=tournament_id)
                request.data['match_number'] = tournament.serial_number or 1
            except Tournament.DoesNotExist:
                pass

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            match = serializer.save()
            return Response(
                {'success': True, 'data': self.get_serializer(match).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        if serializer.is_valid():
            serializer.save()
            return Response({'success': True, 'data': serializer.data})
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {'success': True, 'message': 'Match deleted'},
            status=status.HTTP_200_OK,
        )

# ═══════════════════════════════════════════════════════════
# ✅ ADMIN RESULT UPLOAD VIEW (FIXED)
# ═══════════════════════════════════════════════════════════

class AdminResultUploadView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        match_id = request.data.get('match_id')
        tournament_id = request.data.get('tournament_id')
        file = request.FILES.get('screenshot')

        if not match_id or not file:
            return Response(
                {'success': False, 'error': {'message': 'match_id aur screenshot chahiye'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            match = Match.objects.select_related('tournament').get(id=match_id)
        except Match.DoesNotExist:
            return Response(
                {'success': False, 'error': {'message': 'Match not found'}},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            'success': True,
            'message': 'Single upload API working',
        })

# ═══════════════════════════════════════════════════════════
# ✅ BULK SAVE RESULTS (48 Players / Multi-Image) — FIXED
# ═══════════════════════════════════════════════════════════

class AdminResultBulkSaveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        match_id = request.data.get('match_id')
        results_data = request.data.get('results', [])

        per_kill_amount = float(request.data.get('per_kill_amount', 0) or 0)
        first_bonus = float(request.data.get('first_place_bonus', 0) or 0)
        second_bonus = float(request.data.get('second_place_bonus', 0) or 0)
        third_bonus = float(request.data.get('third_place_bonus', 0) or 0)

        if not match_id:
            return Response({'success': False, 'error': {'message': 'match_id required'}}, status=400)

        if not results_data:
            return Response({'success': False, 'error': {'message': 'No results provided'}}, status=400)

        try:
            match = Match.objects.select_related('tournament').get(id=match_id)
        except Match.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Match not found'}}, status=404)

        if isinstance(results_data, str):
            try:
                results_data = json.loads(results_data)
            except Exception as e:
                return Response({'success': False, 'error': {'message': f'Invalid JSON: {e}'}}, status=400)

        saved = []
        errors = []
        result_objects = []

        with transaction.atomic():
            Result.objects.filter(match=match).delete()

            for r in results_data:
                try:
                    user_email = (r.get('user_email') or '').strip().lower()
                    free_fire_uid = (r.get('free_fire_uid') or '').strip()
                    player_name = (r.get('player_name') or r.get('name') or '').strip()

                    user = None
                    if user_email:
                        user = User.objects.filter(email=user_email).first()
                    if not user and free_fire_uid:
                        user = User.objects.filter(free_fire_uid=free_fire_uid).first()

                    kills = int(r.get('kills', 0) or 0)
                    placement = int(r.get('rank', 0) or r.get('placement', 0) or 0)

                    prize = kills * per_kill_amount
                    if placement == 1: prize += first_bonus
                    elif placement == 2: prize += second_bonus
                    elif placement == 3: prize += third_bonus

                    score = kills * 10
                    if placement == 1: score += 20
                    elif placement == 2: score += 15
                    elif placement == 3: score += 10
                    elif placement > 0: score += 5

                    points_earned = 0
                    if kills == 0:
                        entry_fee_val = float(match.tournament.entry_fee or 0)
                        points_earned = int(entry_fee_val / 5)

                    result_obj = Result(
                        match=match,
                        user=user,
                        free_fire_uid=free_fire_uid,
                        player_name=player_name or (user.display_name if user else 'Unknown'),
                        kills=kills,
                        placement=placement,
                        score=score,
                        prize_amount=prize,
                        per_kill_prize=per_kill_amount,
                        entry_fee=match.tournament.entry_fee,
                        points_earned=points_earned,
                        verification_status=Result.VerificationStatus.PUBLISHED,
                        published_at=timezone.now(),
                    )
                    result_objects.append(result_obj)

                    saved.append({
                        'player_name': result_obj.player_name,
                        'kills': kills,
                        'placement': placement,
                        'points_earned': points_earned,
                    })

                    if user:
                        if points_earned > 0:
                            user.add_points(points_earned)
                        if not user.has_played_first_match:
                            user.has_played_first_match = True
                            user.save(update_fields=['has_played_first_match'])

                except Exception as e:
                    logger.exception(f'Save error: {e}')
                    errors.append({'data': r, 'error': str(e)})

            Result.objects.bulk_create(result_objects)

            # ✅ FCM & DB Notification (Bulk)
            for res in result_objects:
                if res.user:
                    try:
                        # 1. FCM Push (Result Published)
                        if res.user.fcm_token:
                            msg = messaging.Message(
                                notification=messaging.Notification(
                                    title='🏆 Result Announced!',
                                    body=f'Kills: {res.kills}, Prize: ₹{res.prize_amount}'
                                ),
                                data={
                                    'type': 'result_published',
                                    'screen': 'result',
                                    'match_id': str(match.id),
                                },
                                android=messaging.AndroidConfig(
                                    priority='high',
                                    notification=messaging.AndroidNotification(
                                        channel_id='result_channel_v2',
                                        sound='result',
                                    ),
                                ),
                                token=res.user.fcm_token,
                            )
                            messaging.send(msg)
                        
                        # 2. DB Notification (UserNotification)
                        UserNotification.objects.create(
                            user=res.user, type='result_published',
                            title='🏆 Result Announced!',
                            message=f'Aapka result aa gaya!\n\nKills: {res.kills}\nPrize: ₹{res.prize_amount}',
                        )

                    except Exception as e:
                        logger.exception(f'Notification failed: {e}')

        return Response({
            'success': True,
            'message': f'{len(result_objects)} results saved & published',
            'data': {
                'saved': saved,
                'total_saved': len(result_objects),
                'total_errors': len(errors),
                'errors': errors,
            }
        })

# ═══════════════════════════════════════════════════════════
# DELETE RESULT
# ═══════════════════════════════════════════════════════════

class AdminResultDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, result_id):
        try:
            result = Result.objects.get(id=result_id)
        except Result.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Result not found'}}, status=404)

        result.delete()
        return Response({'success': True, 'message': 'Result deleted'})

# ═══════════════════════════════════════════════════════════
# PUBLISH RESULTS (FIXED)
# ═══════════════════════════════════════════════════════════

class AdminPublishResultsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, match_id):
        match = get_object_or_404(Match, id=match_id)
        tournament = match.tournament

        results = Result.objects.filter(match=match)
        published_count = 0

        for result in results:
            try:
                result.verification_status = Result.VerificationStatus.PUBLISHED
                result.published_at = timezone.now()
                result.save(update_fields=['verification_status', 'published_at'])
                published_count += 1

                if result.user:
                    # 1. DB Notification
                    UserNotification.objects.create(
                        user=result.user, type='result_published',
                        title='🏆 Result Announced!',
                        message=f'Aapka result aa gaya!\n\nKills: {result.kills}\nPrize: ₹{result.prize_amount}',
                    )
                    
                    # 2. FCM
                    if result.user.fcm_token:
                        msg = messaging.Message(
                            notification=messaging.Notification(
                                title='🏆 Result Announced!',
                                body=f'Kills: {result.kills}, Prize: ₹{result.prize_amount}'
                            ),
                            data={'type': 'result_published', 'screen': 'result', 'match_id': str(match.id)},
                            android=messaging.AndroidConfig(
                                priority='high',
                                notification=messaging.AndroidNotification(
                                    channel_id='result_channel_v2',
                                    sound='result',
                                ),
                            ),
                            token=result.user.fcm_token,
                        )
                        messaging.send(msg)
            except Exception as e:
                logger.exception(f"Notification failed: {e}")

        return Response({
            'success': True,
            'message': f'{published_count} results published',
            'data': {'published_count': published_count},
        })

# ═══════════════════════════════════════════════════════════
# MATCH RESULTS
# ═══════════════════════════════════════════════════════════

class AdminMatchResultsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, match_id):
        results = Result.objects.filter(
            match_id=match_id
        ).select_related('user').order_by('placement', '-kills')

        data = [
            {
                'id': str(r.id),
                'user_email': r.user.email if r.user else '',
                'user_name': r.player_name or (r.user.display_name if r.user else 'Unknown'),
                'user_mobile': getattr(r.user, 'mobile_number', '') if r.user else '',
                'user_upi_id': getattr(r.user, 'upi_id', '') if r.user else '',
                'free_fire_uid': r.free_fire_uid,
                'kills': r.kills,
                'placement': r.placement,
                'rank': r.placement,
                'prize': str(r.prize_amount),
                'prize_amount': str(r.prize_amount),
                'points_earned': r.points_earned,
                'verification_status': r.verification_status,
                'is_paid': getattr(r, 'is_paid', False),
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]
        return Response({'success': True, 'data': data})

# ═══════════════════════════════════════════════════════════
# PAYMENTS
# ═══════════════════════════════════════════════════════════

class AdminPaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
    queryset = PaymentScreenshot.objects.all().order_by('-uploaded_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        status_filter = request.query_params.get('status')
        if status_filter:
            status_map = {
                'PENDING': 'pending',
                'VERIFIED': 'verified',
                'REJECTED': 'rejected',
                'MANUAL_REVIEW': 'manual_review',
            }
            mapped = status_map.get(status_filter.upper(), status_filter.lower())
            queryset = queryset.filter(status=mapped)

        data = [
            {
                'id': str(p.id),
                'user_email': p.uploaded_by.email if p.uploaded_by else '',
                'user_name': getattr(p.uploaded_by, 'display_name', '') or '',
                'amount': str(p.amount),
                'transaction_id': p.transaction_id,
                'status': p.status,
                'fraud_score': p.fraud_score,
                'image_url': p.image.url if p.image else '',
                'uploaded_at': p.uploaded_at.isoformat(),
                'ocr_confidence': p.ocr_confidence,
            }
            for p in queryset
        ]
        return Response({'success': True, 'data': data})

class AdminVerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, payment_id):
        payment = get_object_or_404(PaymentScreenshot, id=payment_id)
        action = request.data.get('action', '').upper()

        if action == 'APPROVE':
            payment.status = 'verified'
            payment.save()

            # ✅ Notification
            if payment.tournament:
                UserNotification.objects.create(
                    user=payment.uploaded_by, type='payment_verified',
                    title='✅ Payment Verified!',
                    message=f'Aapka payment verify ho gaya. Tournament: {payment.tournament.title}',
                )

            return Response({'success': True, 'message': 'Payment verified'})

        elif action == 'REJECT':
            payment.status = 'rejected'
            payment.save()

            if payment.tournament:
                UserNotification.objects.create(
                    user=payment.uploaded_by, type='payment_rejected',
                    title='❌ Payment Rejected',
                    message=f'Aapka payment reject ho gaya. Reason: {request.data.get("reason", "N/A")}',
                )

            return Response({'success': True, 'message': 'Payment rejected'})

        return Response({'success': False, 'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

# ═══════════════════════════════════════════════════════════
# USERS
# ═══════════════════════════════════════════════════════════

class AdminUserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
    queryset = User.objects.all().order_by('-created_at')

    def get_serializer_class(self):
        from apps.users.serializers import UserSerializer
        return UserSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        status_filter = request.query_params.get('status')
        role_filter = request.query_params.get('role')
        search = request.query_params.get('search')

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if role_filter:
            queryset = queryset.filter(role=role_filter)
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(mobile_number__icontains=search) |
                Q(display_name__icontains=search)
            )

        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'data': serializer.data})


class UserSearchView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        mobile = request.query_params.get('mobile')
        uid = request.query_params.get('free_fire_uid')
        email = request.query_params.get('email')

        queryset = User.objects.all()
        if mobile:
            queryset = queryset.filter(mobile_number__icontains=mobile)
        if uid:
            queryset = queryset.filter(free_fire_uid__icontains=uid)
        if email:
            queryset = queryset.filter(email__icontains=email)

        from apps.users.serializers import UserSerializer
        serializer = UserSerializer(queryset[:20], many=True)
        return Response({'success': True, 'data': serializer.data})


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        from apps.users.serializers import UserSerializer
        serializer = UserSerializer(user)
        return Response({'success': True, 'data': serializer.data})


class AdminBlockUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        action = request.data.get('action')
        reason = request.data.get('reason', '')

        if action == 'BLOCK':
            user.is_active = False
            user.save()

            UserNotification.objects.create(
                user=user, type='account_blocked',
                title='🚫 Account Suspended',
                message=f'Aapka account suspend kar diya gaya hai. Reason: {reason}',
            )

            return Response({'success': True, 'message': 'User blocked'})

        elif action == 'UNBLOCK':
            user.is_active = True
            user.save()
            return Response({'success': True, 'message': 'User unblocked'})

        return Response({'success': False, 'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class AdminUserRoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        role = request.data.get('role')
        user.role = role
        user.save()
        return Response({'success': True, 'message': 'Role updated'})


class AdminToggleCanPlayView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, registration_id):
        reg = get_object_or_404(Registration, id=registration_id)
        can_play = request.data.get('can_play', False)
        reg.can_play = can_play

        if can_play:
            reg.status = Registration.Status.CONFIRMED
            reg.save(update_fields=['can_play', 'status'])
            UserNotification.objects.create(
                user=reg.user, type='can_play_approved',
                title='✅ You Can Play!',
                message=f'Aapko {reg.tournament.title} me khelne ki permission mil gayi.',
            )
        else:
            reg.save(update_fields=['can_play'])

        return Response({
            'success': True,
            'data': {
                'can_play': can_play,
                'status': reg.status,
            },
        })

# ═══════════════════════════════════════════════════════════
# NOTIFICATIONS (Admin Bulk Send) — FIXED
# ═══════════════════════════════════════════════════════════

class AdminNotificationViewSet(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        return Response({'success': True, 'data': []})

    def post(self, request):
        # ✅ Naya code: Celery Worker ko call karega
        title = request.data.get('title')
        message = request.data.get('message')
        user_ids = request.data.get('user_ids', [])
        notif_type = request.data.get('type', 'system')

        if not title or not message:
            return Response({'success': False, 'error': {'message': 'Title and message required'}}, status=400)

        if user_ids == "all":
            user_ids = list(User.objects.values_list('id', flat=True))
        elif isinstance(user_ids, str):
            user_ids = [user_ids]

        if not user_ids:
            return Response({'success': False, 'error': {'message': 'No users selected'}}, status=400)

        # ✅ Background Task
        send_bulk_notifications_task.delay(user_ids, title, message, notif_type)

        return Response({
            'success': True,
            'message': f'Notification bhejna shuru ho gaya {len(user_ids)} users ko!'
        })


# ═══════════════════════════════════════════════════════════
# ✅ IN-APP UPDATE (App Version Check)
# ═══════════════════════════════════════════════════════════

class AppVersionCheckView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            from .models import AppVersion
            latest = AppVersion.objects.order_by('-updated_at').first()
            if latest:
                return Response({
                    "success": True,
                    "data": {
                        "latest_version": latest.version,
                        "force_update": latest.is_force_update,
                        "apk_url": latest.apk_url
                    }
                })
            return Response({"success": False, "message": "No version info"})
        except Exception as e:
            return Response({"success": False, "message": str(e)})


class AdminPublishResultsFromTournamentView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, tournament_id):
        tournament = get_object_or_404(Tournament, id=tournament_id)
        match_id = request.data.get('match_id')

        if match_id:
            matches = Match.objects.filter(id=match_id, tournament=tournament)
        else:
            matches = Match.objects.filter(tournament=tournament)

        published_count = 0
        for match in matches:
            results = Result.objects.filter(match=match)
            for result in results:
                try:
                    result.verification_status = Result.VerificationStatus.PUBLISHED
                    result.published_at = timezone.now()
                    result.save(update_fields=['verification_status', 'published_at'])
                    published_count += 1

                    if result.user:
                        UserNotification.objects.create(
                            user=result.user, type='result_published',
                            title='🏆 Result Announced!',
                            message=f'Aapka result aa gaya!\n\nKills: {result.kills}\nPrize: ₹{result.prize_amount}',
                        )
                        
                        if result.user.fcm_token:
                            msg = messaging.Message(
                                notification=messaging.Notification(
                                    title='🏆 Result Announced!',
                                    body=f'Kills: {result.kills}, Prize: ₹{result.prize_amount}'
                                ),
                                data={'type': 'result_published', 'screen': 'result', 'match_id': str(match.id)},
                                android=messaging.AndroidConfig(
                                    priority='high',
                                    notification=messaging.AndroidNotification(
                                        channel_id='result_channel_v2',
                                        sound='result',
                                    ),
                                ),
                                token=result.user.fcm_token,
                            )
                            messaging.send(msg)
                except Exception as e:
                    logger.exception(f"Notification failed: {e}")

        return Response({
            'success': True,
            'message': f'{published_count} results published',
            'data': {'published_count': published_count},
        })