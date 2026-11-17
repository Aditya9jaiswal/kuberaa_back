# apps/tournaments/views.py

from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
import logging

from core.responses import success_response, error_response
from core.pagination import StandardPagination
from core.permissions import IsAdminRole
from .models import Tournament, Registration, MatchRoom
from .serializers import (
    TournamentSerializer,
    TournamentListSerializer,
    RegistrationSerializer,
    MyRegistrationDetailSerializer,
)
from .services import TournamentService

# ✅ Cache imports
from apps.results.cache_utils import (
    get_cached_tournaments_list,
    set_cached_tournaments_list,
    get_cached_tournament_detail,
    set_cached_tournament_detail,
    invalidate_tournament_cache,
    invalidate_notifications_cache,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# USER APIs
# ═══════════════════════════════════════════════════════════

class TournamentListView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminRole()]
        return [AllowAny()]

    def get(self, request):
        # ✅ Cache check
        page_num = request.query_params.get('page', '1')
        cache_suffix = f'page_{page_num}'

        cached = get_cached_tournaments_list(cache_suffix)
        if cached is not None:
            logger.info(f'⚡ Cache HIT: tournaments_list_{cache_suffix}')
            return Response(cached)

        logger.info(f'💾 Cache MISS → DB: tournaments_list_{cache_suffix}')

        qs = Tournament.objects.exclude(
            status=Tournament.Status.DRAFT
        ).order_by('-serial_number')

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)

        serializer = TournamentListSerializer(
            page,
            many=True,
            context={'request': request},
        )
        response_data = paginator.get_paginated_response(serializer.data).data

        # ✅ Cache 5 min
        set_cached_tournaments_list(response_data, filters=cache_suffix, timeout=300)

        return Response(response_data)

    def post(self, request):
        serializer = TournamentSerializer(
            data=request.data,
            context={'request': request},
        )
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)
        tournament = serializer.save(created_by=request.user)

        # ✅ Cache invalidate
        invalidate_tournament_cache(tournament.id)

        return success_response(
            data=TournamentSerializer(
                tournament, context={'request': request}
            ).data,
            message=f'Tournament #{tournament.display_id} created',
            status=201,
        )


class TournamentDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ['PATCH', 'PUT']:
            return [IsAuthenticated(), IsAdminRole()]
        return [AllowAny()]

    def get(self, request, pk):
        # ✅ Cache check
        cached = get_cached_tournament_detail(pk)
        if cached is not None:
            logger.info(f'⚡ Cache HIT: tournament_detail_{pk}')
            return success_response(data=cached)

        logger.info(f'💾 Cache MISS → DB: tournament_detail_{pk}')

        try:
            tournament = Tournament.objects.get(id=pk)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        data = TournamentSerializer(
            tournament, context={'request': request}
        ).data

        # ✅ Cache 5 min
        set_cached_tournament_detail(pk, data, timeout=300)

        return success_response(data=data)

    def patch(self, request, pk):
        try:
            tournament = Tournament.objects.get(id=pk)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        serializer = TournamentSerializer(
            tournament,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)
        tournament = serializer.save()

        # ✅ Cache invalidate
        invalidate_tournament_cache(tournament.id)

        return success_response(
            data=TournamentSerializer(
                tournament, context={'request': request}
            ).data,
            message='Updated',
        )


class TournamentRegisterView(APIView):
    """Tournament registration — normal + free entry + first free + Kuberaa Points"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        from apps.users.services.referral_service import ReferralService
        from apps.payments.models import UserNotification
        from apps.users.models import User

        referral_code = request.data.get('referral_code', '').strip().upper()
        use_free_entry = request.data.get('use_free_entry', False)
        use_points = request.data.get('use_points', False)

        try:
            tournament = Tournament.objects.get(id=pk)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        entry_fee = float(tournament.entry_fee or 0)
        user = request.user

        # 1. FIRST FREE MATCH
        if (
            not use_free_entry
            and not use_points
            and user.can_use_first_free
            and entry_fee == 10.0
        ):
            logger.info(f'🆕 First FREE match for {user.email}')

            reg, created = Registration.objects.get_or_create(
                tournament=tournament,
                user=user,
                defaults={
                    'free_fire_uid': user.free_fire_uid or '',
                    'free_fire_name': user.free_fire_name or '',
                    'user_upi_id': user.upi_id or '',
                    'user_mobile': user.mobile_number or '',
                    'status': Registration.Status.CONFIRMED,
                    'can_play': False,
                    'is_free_entry': True,
                    'is_first_free': True,
                    'payment_type': Registration.PaymentType.FIRST_FREE,
                    'entry_fee_paid': 0,
                    'points_used': 0,
                },
            )

            user.has_played_first_match = True
            user.first_match_free_used = True
            user.save(update_fields=[
                'has_played_first_match',
                'first_match_free_used',
            ])

            try:
                admins = User.objects.filter(role__in=['SUPER_ADMIN', 'ADMIN'])
                for admin in admins:
                    UserNotification.objects.create(
                        user=admin,
                        type='first_free_approval',
                        title='🆕 NEW USER — FIRST FREE',
                        message=(
                            f'{user.display_name or user.email} '
                            f'ne FIRST FREE match use kiya.\n\n'
                            f'Tournament: {tournament.title}\n'
                            f'Amount: ₹{entry_fee:.0f}'
                        ),
                    )
                    invalidate_notifications_cache(admin.id)
            except Exception as e:
                logger.warning(f'Admin notification failed: {e}')

            return success_response(
                data={
                    **RegistrationSerializer(reg).data,
                    'tournament_display_id': tournament.display_id,
                    'first_free': True,
                    'requires_approval': True,
                    'payment_type': 'FIRST_FREE',
                    'payment_badge': '🆕 NEW USER — FIRST FREE',
                },
                message='🆕 First match FREE! Admin approval ka wait karo.',
                status=201,
            )

        # 2. KUBERAA POINTS
        if use_points:
            points_needed = int(entry_fee)

            if user.kuberaa_points < points_needed:
                return error_response(
                    f'Insufficient Kuberaa Points. '
                    f'Need {points_needed}, have {user.kuberaa_points}',
                    400,
                )

            user.kuberaa_points -= points_needed
            user.save(update_fields=['kuberaa_points'])

            reg, created = Registration.objects.get_or_create(
                tournament=tournament,
                user=user,
                defaults={
                    'free_fire_uid': user.free_fire_uid or '',
                    'free_fire_name': user.free_fire_name or '',
                    'user_upi_id': user.upi_id or '',
                    'user_mobile': user.mobile_number or '',
                    'status': Registration.Status.CONFIRMED,
                    'can_play': False,
                    'is_free_entry': False,
                    'is_first_free': False,
                    'payment_type': Registration.PaymentType.POINTS,
                    'points_used': points_needed,
                    'entry_fee_paid': 0,
                },
            )

            try:
                admins = User.objects.filter(role__in=['SUPER_ADMIN', 'ADMIN'])
                for admin in admins:
                    UserNotification.objects.create(
                        user=admin,
                        type='points_approval',
                        title='🎁 KUBERAA POINTS — Approval Pending',
                        message=(
                            f'{user.display_name or user.email} '
                            f'ne {points_needed} Kuberaa Points use kiye.\n\n'
                            f'Tournament: {tournament.title}'
                        ),
                    )
                    invalidate_notifications_cache(admin.id)
            except Exception as e:
                logger.warning(f'Admin notification failed: {e}')

            return success_response(
                data={
                    **RegistrationSerializer(reg).data,
                    'tournament_display_id': tournament.display_id,
                    'points_used': points_needed,
                    'remaining_points': user.kuberaa_points,
                    'requires_approval': True,
                    'payment_type': 'POINTS',
                    'payment_badge': f'🎁 KUBERAA POINTS ({points_needed} used)',
                },
                message=f'🎁 {points_needed} Kuberaa Points used! Admin approval ka wait karo.',
                status=201,
            )

        # 3. FREE ENTRY
        if not use_free_entry:
            if ReferralService.has_free_entry_available(user):
                max_amt = float(user.free_entry_max_amount or 0)
                if max_amt >= entry_fee and entry_fee > 0:
                    use_free_entry = True
                    logger.info(f'🎁 Auto free entry for {user.email}')

        if use_free_entry:
            try:
                ReferralService.validate_and_use_free_entry(user, tournament)

                reg, created = Registration.objects.get_or_create(
                    tournament=tournament,
                    user=user,
                    defaults={
                        'free_fire_uid': user.free_fire_uid or '',
                        'free_fire_name': user.free_fire_name or '',
                        'user_upi_id': user.upi_id or '',
                        'user_mobile': user.mobile_number or '',
                        'status': Registration.Status.CONFIRMED,
                        'can_play': False,
                        'is_free_entry': True,
                        'is_first_free': False,
                        'payment_type': Registration.PaymentType.FIRST_FREE,
                        'entry_fee_paid': 0,
                        'points_used': 0,
                    },
                )

                try:
                    admins = User.objects.filter(role__in=['SUPER_ADMIN', 'ADMIN'])
                    for admin in admins:
                        UserNotification.objects.create(
                            user=admin,
                            type='free_entry_approval',
                            title='🎁 Free Entry — Approval Pending',
                            message=(
                                f'{user.display_name or user.email} '
                                f'ne FREE ENTRY use ki.\n\n'
                                f'Tournament: {tournament.title}'
                            ),
                        )
                        invalidate_notifications_cache(admin.id)
                except Exception as e:
                    logger.warning(f'Admin notification failed: {e}')

                return success_response(
                    data={
                        **RegistrationSerializer(reg).data,
                        'tournament_display_id': tournament.display_id,
                        'free_entry': True,
                        'requires_approval': True,
                        'payment_type': 'FIRST_FREE',
                        'payment_badge': '🎁 FREE ENTRY',
                    },
                    message='🎁 Free entry applied! Admin approval ka wait karo.',
                    status=201,
                )
            except Exception as e:
                return error_response(str(e), 400)

        # 4. NORMAL PAID FLOW
        free_fire_uid = (
            request.data.get('free_fire_uid')
            or getattr(user, 'free_fire_uid', None)
        )
        free_fire_name = (
            request.data.get('free_fire_name')
            or getattr(user, 'free_fire_name', None)
        )
        user_upi_id = request.data.get('user_upi_id', '').strip()
        user_mobile = request.data.get('user_mobile', '').strip()

        if not free_fire_uid:
            return error_response('Free Fire UID required', 400)
        if not free_fire_name:
            return error_response('Free Fire Name required', 400)
        if not user_upi_id or '@' not in user_upi_id:
            return error_response('Valid UPI ID required', 400)
        if not user_mobile or len(user_mobile) < 10:
            return error_response('Valid mobile number required', 400)

        try:
            reg = TournamentService.register_user_for_tournament(
                pk, user, free_fire_uid, free_fire_name,
                user_upi_id=user_upi_id,
                user_mobile=user_mobile,
                referral_code=referral_code if referral_code else None,
                use_free_entry=False,
            )
            reg.payment_type = Registration.PaymentType.CASH
            reg.save(update_fields=['payment_type'])
        except Exception as e:
            return error_response(str(e), 400)

        # ✅ Cache invalidate
        invalidate_tournament_cache(pk)
        cache.delete(f'my_registrations_{user.id}')

        return success_response(
            data={
                **RegistrationSerializer(reg).data,
                'tournament_entry_fee': float(reg.tournament.entry_fee),
                'tournament_upi_id': reg.tournament.upi_id,
                'tournament_upi_name': reg.tournament.upi_name,
                'tournament_display_id': reg.tournament.display_id,
                'free_entry': False,
                'payment_type': 'CASH',
                'payment_badge': '💰 CASH PAYMENT',
            },
            message='Registration created. Complete payment.',
            status=201,
        )


# ═══════════════════════════════════════════════════════════
# MY REGISTRATIONS (cache)
# ═══════════════════════════════════════════════════════════

class MyRegistrationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.results.models import Result
        from apps.matches.models import Match

        # ✅ Cache check
        cache_key = f'my_registrations_{request.user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f'⚡ Cache HIT: my_registrations_{request.user.id}')
            return success_response(data=cached)

        logger.info(f'💾 Cache MISS → DB: my_registrations_{request.user.id}')

        qs = Registration.objects.filter(
            user=request.user
        ).select_related('tournament').order_by('-created_at')

        data = []

        for reg in qs:
            t = reg.tournament

            match = Match.objects.filter(
                tournament=t
            ).order_by('-match_number').first()

            match_status = match.status if match else 'UNKNOWN'
            is_match_completed = match_status == 'COMPLETED'

            my_result = None
            has_result = False

            if match and is_match_completed:
                result_obj = Result.objects.filter(
                    match=match,
                    user=request.user,
                    verification_status=Result.VerificationStatus.PUBLISHED,
                ).first()

                if result_obj:
                    has_result = True
                    my_result = {
                        'id': str(result_obj.id),
                        'match_id': str(match.id),
                        'match_title': (
                            match.title or f'Match {match.match_number}'
                        ),
                        'tournament_title': t.title,
                        'player_name': result_obj.player_name,
                        'kills': result_obj.kills,
                        'placement': result_obj.placement,
                        'score': result_obj.score,
                        'prize_amount': float(result_obj.prize_amount),
                        'per_kill_prize': float(
                            result_obj.per_kill_prize or 0
                        ),
                        'is_paid': result_obj.is_paid,
                        'free_fire_uid': result_obj.free_fire_uid,
                        'match_status': match_status,
                        'tournament_status': t.status,
                    }

            room_data = None
            try:
                room = t.match_room
                room_data = {
                    'room_id': room.room_id,
                    'room_password': room.room_password,
                    'scheduled_at': (
                        room.scheduled_at.isoformat()
                        if room.scheduled_at else None
                    ),
                }
            except Exception:
                pass

            data.append({
                'registration_id': str(reg.id),
                'status': reg.status,
                'can_play': reg.can_play,
                'is_free_entry': getattr(reg, 'is_free_entry', False),
                'is_first_free': getattr(reg, 'is_first_free', False),
                'payment_type': getattr(reg, 'payment_type', 'CASH'),
                'points_used': getattr(reg, 'points_used', 0),
                'free_fire_uid': reg.free_fire_uid,
                'free_fire_name': reg.free_fire_name,
                'user_upi_id': reg.user_upi_id,
                'user_mobile': reg.user_mobile,
                'created_at': reg.created_at.isoformat(),
                'room': room_data,
                'has_result': has_result,
                'my_result': my_result,
                'is_match_completed': is_match_completed,
                'match_status': match_status,
                'tournament': {
                    'id': str(t.id),
                    'display_id': t.display_id,
                    'title': t.title,
                    'entry_fee': str(t.entry_fee),
                    'upi_id': t.upi_id,
                    'upi_name': t.upi_name,
                    'tournament_date': str(t.tournament_date),
                    'start_time': (
                        t.start_time.isoformat() if t.start_time else None
                    ),
                    'status': t.status,
                    'current_participants': t.current_participants,
                    'maximum_participants': t.maximum_participants,
                },
            })

        # ✅ Cache 2 min
        cache.set(cache_key, data, timeout=120)

        return success_response(data=data)


# ═══════════════════════════════════════════════════════════
# MATCH ROOM
# ═══════════════════════════════════════════════════════════

class MyMatchRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from apps.matches.models import Match
        from apps.results.models import Result

        reg = Registration.objects.filter(
            tournament_id=pk, user=request.user,
        ).select_related('tournament').first()

        if not reg:
            return error_response(
                'Aap is tournament ke liye registered nahi ho', 403
            )

        if not reg.can_play:
            return error_response(
                'Admin ne aapko abhi approve nahi kiya', 403
            )

        tournament = reg.tournament

        match = Match.objects.filter(
            tournament=tournament
        ).order_by('-match_number').first()

        match_status = match.status if match else 'UNKNOWN'
        is_match_completed = match_status == 'COMPLETED'

        my_result = None
        has_result = False
        if match:
            result_obj = Result.objects.filter(
                match=match,
                user=request.user,
                verification_status=Result.VerificationStatus.PUBLISHED,
            ).first()

            if result_obj:
                has_result = True
                my_result = {
                    'id': str(result_obj.id),
                    'match_id': str(match.id),
                    'match_title': (
                        match.title or f'Match {match.match_number}'
                    ),
                    'tournament_title': tournament.title,
                    'player_name': result_obj.player_name,
                    'kills': result_obj.kills,
                    'placement': result_obj.placement,
                    'score': result_obj.score,
                    'prize_amount': float(result_obj.prize_amount),
                    'per_kill_prize': float(result_obj.per_kill_prize or 0),
                    'is_paid': result_obj.is_paid,
                    'free_fire_uid': result_obj.free_fire_uid,
                    'match_status': match_status,
                    'tournament_status': tournament.status,
                }

        room_data = {
            'is_revealed': False,
            'reveal_at': None,
            'time_until_reveal_seconds': 0,
            'minutes_until_start': 0,
            'room_id': '',
            'room_password': '',
            'scheduled_at': None,
            'notes': '',
            'room_updated_at': None,
        }

        if not is_match_completed:
            try:
                room = MatchRoom.objects.get(tournament_id=pk)

                if room.room_id and room.room_password:
                    now = timezone.now()
                    start_time = tournament.start_time
                    reveal_time = start_time - timedelta(minutes=5)

                    is_revealed = now >= reveal_time

                    time_until_reveal = 0
                    if not is_revealed:
                        time_until_reveal = max(
                            0,
                            int((reveal_time - now).total_seconds()),
                        )

                    minutes_until_start = max(
                        0,
                        int((start_time - now).total_seconds() / 60),
                    )

                    room_data.update({
                        'is_revealed': is_revealed,
                        'reveal_at': reveal_time.isoformat(),
                        'time_until_reveal_seconds': time_until_reveal,
                        'minutes_until_start': minutes_until_start,
                        'scheduled_at': (
                            room.scheduled_at.isoformat()
                            if room.scheduled_at else None
                        ),
                        'notes': room.notes,
                        'room_updated_at': (
                            room.updated_at.isoformat()
                            if room.updated_at else None
                        ),
                    })

                    if is_revealed:
                        room_data['room_id'] = room.room_id
                        room_data['room_password'] = room.room_password
            except MatchRoom.DoesNotExist:
                pass

        return success_response(data={
            'match_status': match_status,
            'is_match_completed': is_match_completed,
            'tournament_status': tournament.status,
            'has_result': has_result,
            'my_result': my_result,
            **room_data,
            'title': tournament.title,
            'display_id': tournament.display_id,
            'rules': tournament.rules,
            'match_number': match.match_number if match else 1,
            'start_time': (
                tournament.start_time.isoformat()
                if tournament.start_time else None
            ),
            'my_registration': {
                'id': str(reg.id),
                'status': reg.status,
                'can_play': reg.can_play,
                'is_free_entry': getattr(reg, 'is_free_entry', False),
                'is_first_free': getattr(reg, 'is_first_free', False),
                'payment_type': getattr(reg, 'payment_type', 'CASH'),
                'points_used': getattr(reg, 'points_used', 0),
                'free_fire_uid': reg.free_fire_uid,
                'free_fire_name': reg.free_fire_name,
                'user_upi_id': reg.user_upi_id,
                'user_mobile': reg.user_mobile,
                'room_id': room_data['room_id'],
                'room_password': room_data['room_password'],
                'room_updated_at': room_data['room_updated_at'],
            },
        })


# ═══════════════════════════════════════════════════════════
# ADMIN APIs
# ═══════════════════════════════════════════════════════════

class AdminTournamentListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        status_filter = request.query_params.get('status')

        # ✅ Cache check
        cache_key = f'admin_tournaments_{status_filter or "all"}'
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f'⚡ Cache HIT: {cache_key}')
            return success_response(data=cached)

        logger.info(f'💾 Cache MISS → DB: {cache_key}')

        qs = Tournament.objects.all().order_by('-serial_number')

        if status_filter and status_filter != 'ALL':
            qs = qs.filter(status=status_filter)

        data = []
        for t in qs:
            confirmed_regs = t.registrations.filter(
                status=Registration.Status.CONFIRMED
            )
            can_play_regs = t.registrations.filter(can_play=True)
            data.append({
                'id': str(t.id),
                'display_id': t.display_id,
                'title': t.title,
                'description': t.description,
                'rules': t.rules,
                'prize_info': t.prize_info,
                'entry_fee': float(t.entry_fee),
                'upi_id': t.upi_id,
                'upi_name': t.upi_name,
                'tournament_date': str(t.tournament_date),
                'start_time': str(t.start_time),
                'registration_start': str(t.registration_start),
                'registration_end': str(t.registration_end),
                'maximum_participants': t.maximum_participants,
                'current_participants': t.current_participants,
                'slots_left': t.slots_left,
                'status': t.status,
                'matches_count': (
                    getattr(t, 'matches', None).count()
                    if hasattr(t, 'matches') else 0
                ),
                'confirmed_participants': confirmed_regs.count(),
                'can_play_participants': can_play_regs.count(),
                'total_registrations': t.registrations.count(),
                'created_at': str(t.created_at),
            })

        # ✅ Cache 2 min
        cache.set(cache_key, data, timeout=120)

        return success_response(data=data)


class AdminTournamentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        # ✅ Cache check
        cache_key = f'admin_tournament_detail_{pk}'
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f'⚡ Cache HIT: {cache_key}')
            return success_response(data=cached)

        logger.info(f'💾 Cache MISS → DB: {cache_key}')

        try:
            tournament = Tournament.objects.get(id=pk)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        try:
            from apps.matches.models import Match
            from apps.matches.serializers import MatchAdminSerializer
            matches = Match.objects.filter(
                tournament=tournament
            ).order_by('match_number')
            matches_data = MatchAdminSerializer(matches, many=True).data
        except ImportError:
            matches_data = []

        registrations = Registration.objects.filter(
            tournament=tournament,
        ).select_related('user').order_by('-created_at')

        from apps.payments.models import PaymentScreenshot

        regs_data = []
        for reg in registrations:
            payment = PaymentScreenshot.objects.filter(
                uploaded_by=reg.user,
                tournament_id=tournament.id,
            ).order_by('-uploaded_at').first()

            utr = payment.transaction_id if payment else ''
            payment_app = (
                getattr(payment, 'payment_app', '') if payment else ''
            )

            is_duplicate = False
            duplicate_info = ''
            if utr:
                other = PaymentScreenshot.objects.filter(
                    transaction_id=utr
                ).exclude(uploaded_by=reg.user).first()
                if other:
                    is_duplicate = True
                    duplicate_info = other.uploaded_by.email

            screenshot_duplicate = False
            if payment and payment.image:
                image_name = str(payment.image.name).split('/')[-1]
                other_img = PaymentScreenshot.objects.filter(
                    image__endswith=image_name
                ).exclude(id=payment.id).first()
                if other_img:
                    screenshot_duplicate = True

            regs_data.append({
                'id': str(reg.id),
                'user_id': str(reg.user.id),
                'user_email': reg.user.email,
                'user_name': (
                    getattr(reg.user, 'display_name', '')
                    or reg.user.email
                ),
                'user_mobile': getattr(reg, 'user_mobile', ''),
                'free_fire_uid': reg.free_fire_uid,
                'free_fire_name': reg.free_fire_name,
                'user_upi_id': reg.user_upi_id,
                'status': reg.status,
                'can_play': reg.can_play,
                'is_free_entry': getattr(reg, 'is_free_entry', False),
                'is_first_free': getattr(reg, 'is_first_free', False),
                'payment_type': getattr(reg, 'payment_type', 'CASH'),
                'points_used': getattr(reg, 'points_used', 0),
                'payment_badge': (
                    '🆕 NEW USER — FIRST FREE'
                    if getattr(reg, 'is_first_free', False)
                    else f'🎁 KUBERAA POINTS ({getattr(reg, "points_used", 0)} used)'
                    if getattr(reg, 'payment_type', '') == 'POINTS'
                    else '🎁 FREE ENTRY'
                    if getattr(reg, 'is_free_entry', False)
                    else '💰 CASH PAYMENT'
                ),
                'entry_fee_paid': float(getattr(reg, 'entry_fee_paid', 0) or 0),
                'amount': float(tournament.entry_fee),
                'entry_fee': str(tournament.entry_fee),
                'transaction_id': utr,
                'utr': utr,
                'payment_app': payment_app,
                'payment_status': (
                    payment.status if payment else 'NO_PAYMENT'
                ),
                'payment_id': str(payment.id) if payment else None,
                'is_duplicate': is_duplicate,
                'duplicate_info': duplicate_info,
                'screenshot_duplicate': screenshot_duplicate,
                'created_at': str(reg.created_at),
            })

        room_data = None
        if hasattr(tournament, 'match_room'):
            room = tournament.match_room
            room_data = {
                'room_id': room.room_id,
                'room_password': room.room_password,
                'scheduled_at': (
                    str(room.scheduled_at) if room.scheduled_at else None
                ),
                'notes': room.notes,
            }

        response_data = {
            'tournament': TournamentSerializer(
                tournament, context={'request': request}
            ).data,
            'matches': matches_data,
            'match_room': room_data,
            'registrations': regs_data,
            'total_registrations': len(regs_data),
            'confirmed': registrations.filter(
                status=Registration.Status.CONFIRMED
            ).count(),
            'can_play': registrations.filter(can_play=True).count(),
            'pending_payment': registrations.filter(
                status=Registration.Status.PENDING_PAYMENT
            ).count(),
            'payment_submitted': registrations.filter(
                status=Registration.Status.PAYMENT_SUBMITTED
            ).count(),
        }

        # ✅ Cache 2 min
        cache.set(cache_key, response_data, timeout=120)

        return success_response(data=response_data)

    def patch(self, request, pk):
        try:
            tournament = Tournament.objects.get(id=pk)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        serializer = TournamentSerializer(
            tournament,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)
        tournament = serializer.save()

        # ✅ Cache invalidate
        invalidate_tournament_cache(tournament.id)
        cache.delete(f'admin_tournament_detail_{pk}')

        return success_response(
            data=TournamentSerializer(
                tournament, context={'request': request}
            ).data,
            message='Tournament updated',
        )

    def delete(self, request, pk):
        try:
            tournament = Tournament.objects.get(id=pk)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        display_id = tournament.display_id
        tournament.delete()

        # ✅ Cache invalidate
        invalidate_tournament_cache(pk)
        cache.delete(f'admin_tournament_detail_{pk}')

        return success_response(
            message=f'Tournament #{display_id} deleted',
        )


class AdminMatchRoomView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            tournament = Tournament.objects.get(id=pk)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        try:
            room = MatchRoom.objects.get(tournament=tournament)
            return success_response(data={
                'room_id': room.room_id or '',
                'room_password': room.room_password or '',
                'scheduled_at': (
                    str(room.scheduled_at) if room.scheduled_at else None
                ),
                'notes': room.notes or '',
                'updated_at': (
                    str(room.updated_at) if room.updated_at else None
                ),
            })
        except MatchRoom.DoesNotExist:
            return success_response(data={
                'room_id': '',
                'room_password': '',
                'scheduled_at': None,
                'notes': '',
                'updated_at': None,
            })

    def post(self, request, pk):
        from apps.notifications.services import NotificationService

        try:
            tournament = Tournament.objects.get(id=pk)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        room, _ = MatchRoom.objects.get_or_create(tournament=tournament)
        room.room_id = request.data.get('room_id', room.room_id)
        room.room_password = request.data.get(
            'room_password', room.room_password
        )
        room.notes = request.data.get('notes', room.notes)

        scheduled = request.data.get('scheduled_at')
        if scheduled:
            from django.utils.dateparse import parse_datetime
            room.scheduled_at = parse_datetime(scheduled)

        room.save()

        # ✅ Cache invalidate
        cache.delete(f'tournament_detail_{pk}')
        cache.delete(f'admin_tournament_detail_{pk}')

        try:
            regs = Registration.objects.filter(
                tournament=tournament,
                can_play=True,
            )
            for reg in regs:
                NotificationService.send_room_released(
                    reg.user, tournament, room_id=room.room_id,
                )
        except Exception as e:
            logger.exception(f"Notification failed: {e}")

        return success_response(data={
            'room_id': room.room_id,
            'room_password': room.room_password,
            'scheduled_at': (
                str(room.scheduled_at) if room.scheduled_at else None
            ),
            'notes': room.notes,
            'updated_at': (
                str(room.updated_at) if room.updated_at else None
            ),
        }, message='Room saved')


class AdminToggleCanPlayView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, registration_id):
        try:
            reg = Registration.objects.get(id=registration_id)
        except Registration.DoesNotExist:
            return error_response('Registration not found', 404)

        reg.can_play = request.data.get('can_play', True)
        if reg.can_play:
            reg.status = Registration.Status.CONFIRMED
        reg.save(update_fields=['can_play', 'status'])

        # ✅ Cache invalidate
        cache.delete(f'my_registrations_{reg.user.id}')
        cache.delete(f'admin_tournament_detail_{reg.tournament.id}')

        return success_response(data={
            'registration_id': str(reg.id),
            'can_play': reg.can_play,
            'status': reg.status,
        })


# ═══════════════════════════════════════════════════════════
# ADMIN — FREE ENTRY APPROVE / REJECT
# ═══════════════════════════════════════════════════════════

class AdminApproveFreeEntryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, registration_id):
        try:
            reg = Registration.objects.get(
                id=registration_id,
                is_free_entry=True,
            )
        except Registration.DoesNotExist:
            return error_response('Free entry registration not found', 404)

        action = request.data.get('action', 'approve')
        from apps.payments.models import UserNotification

        if action == 'approve':
            reg.can_play = True
            reg.status = Registration.Status.CONFIRMED
            reg.save(update_fields=['can_play', 'status'])

            try:
                UserNotification.objects.create(
                    user=reg.user,
                    type='free_entry_approved',
                    title='✅ Free Entry Approved!',
                    message=(
                        f'Aapki free entry approve ho gayi!\n\n'
                        f'🏆 {reg.tournament.title}\n'
                        f'Match join karo aur khelo!'
                    ),
                )
                invalidate_notifications_cache(reg.user.id)
            except Exception as e:
                logger.warning(f'Notification failed: {e}')

            # ✅ Cache invalidate
            cache.delete(f'my_registrations_{reg.user.id}')
            cache.delete(f'admin_tournament_detail_{reg.tournament.id}')

            return success_response(
                data={
                    'registration_id': str(reg.id),
                    'can_play': True,
                    'status': reg.status,
                },
                message='Free entry approved',
            )

        else:  # reject
            reg.can_play = False
            reg.status = Registration.Status.CANCELLED
            reg.save(update_fields=['can_play', 'status'])

            user = reg.user

            if getattr(reg, 'is_first_free', False):
                user.has_played_first_match = False
                user.first_match_free_used = False
                user.save(update_fields=[
                    'has_played_first_match',
                    'first_match_free_used',
                ])
            elif getattr(reg, 'payment_type', '') == 'POINTS':
                points = getattr(reg, 'points_used', 0)
                if points > 0:
                    user.add_points(points)
            else:
                user.free_entry_used = False
                user.free_entry_used_at = None
                user.free_entry_used_tournament = None
                user.save(update_fields=[
                    'free_entry_used',
                    'free_entry_used_at',
                    'free_entry_used_tournament',
                ])

            try:
                UserNotification.objects.create(
                    user=user,
                    type='free_entry_rejected',
                    title='❌ Free Entry Rejected',
                    message=(
                        f'Aapki free entry reject ho gayi.\n\n'
                        f'🏆 {reg.tournament.title}\n'
                        f'Free entry wapas aapke account mein aa gayi hai.'
                    ),
                )
                invalidate_notifications_cache(user.id)
            except Exception:
                pass

            # ✅ Cache invalidate
            cache.delete(f'my_registrations_{user.id}')
            cache.delete(f'admin_tournament_detail_{reg.tournament.id}')

            return success_response(
                data={
                    'registration_id': str(reg.id),
                    'can_play': False,
                    'status': reg.status,
                },
                message='Free entry rejected — wapas mil gayi',
            )


# ═══════════════════════════════════════════════════════════
# ADMIN — RESULTS
# ═══════════════════════════════════════════════════════════

class AdminTournamentResultsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        # ✅ Cache check
        cache_key = f'admin_tournament_results_{pk}'
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f'⚡ Cache HIT: {cache_key}')
            return success_response(data=cached)

        logger.info(f'💾 Cache MISS → DB: {cache_key}')

        try:
            from apps.results.models import Result
        except ImportError:
            return success_response(data=[])

        results = Result.objects.filter(
            match__tournament_id=pk,
        ).select_related('user', 'match').order_by(
            '-score', '-kills', 'placement'
        )

        data = []
        for rank, r in enumerate(results, start=1):
            data.append({
                'id': str(r.id),
                'rank': rank,
                'match_id': str(r.match.id) if r.match else None,
                'match_number': r.match.match_number if r.match else 0,
                'user_id': str(r.user.id) if r.user else None,
                'user_email': r.user.email if r.user else '',
                'free_fire_uid': r.free_fire_uid,
                'player_name': r.player_name,
                'kills': r.kills,
                'placement': r.placement,
                'score': r.score,
                'verification_status': r.verification_status,
                'published_at': (
                    str(r.published_at) if r.published_at else None
                ),
            })

        # ✅ Cache 2 min
        cache.set(cache_key, data, timeout=120)

        return success_response(data=data)


class AdminPublishResultsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            from apps.results.models import Result
            from apps.results.cache_utils import invalidate_match_results_cache
        except ImportError:
            return error_response('Results app not installed', 400)

        match_id = request.data.get('match_id')

        qs = Result.objects.filter(match__tournament_id=pk)
        if match_id:
            qs = qs.filter(match_id=match_id)

        count = qs.update(
            verification_status=Result.VerificationStatus.PUBLISHED,
            published_at=timezone.now(),
        )

        # ✅ Cache invalidate
        if match_id:
            invalidate_match_results_cache(match_id)
        cache.delete(f'admin_tournament_results_{pk}')

        return success_response(message=f'{count} results published')