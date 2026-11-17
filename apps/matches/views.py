# apps/matches/views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import timedelta

from core.responses import success_response, error_response
from core.permissions import IsAdminRole
from .models import Match, MatchParticipant
from .serializers import (
    MatchSerializer,
    MatchAdminSerializer,
    MatchParticipantSerializer,
)

# ✅ Cache imports
from apps.results.cache_utils import (
    get_cached_matches_list,
    set_cached_matches_list,
    get_cached_match_detail,
    set_cached_match_detail,
    get_cached_match_status,
    set_cached_match_status,
    invalidate_match_cache,
    invalidate_match_results_cache,
)


# ==================================================
# USER APIs
# ==================================================

class MatchListView(APIView):
    """GET: list matches for user's confirmed tournaments."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.tournaments.models import Registration

        user_id = request.user.id

        # ✅ Cache key — per user
        cache_suffix = f'user_{user_id}'

        cached = get_cached_matches_list(cache_suffix)
        if cached is not None:
            return success_response(data=cached)

        user_tournaments = Registration.objects.filter(
            user=request.user,
            status='CONFIRMED',
        ).values_list('tournament_id', flat=True)

        qs = Match.objects.filter(
            tournament_id__in=user_tournaments,
        ).order_by('scheduled_start_time')

        data = MatchSerializer(qs, many=True).data

        # ✅ Cache 5 min
        set_cached_matches_list(data, filters=cache_suffix, timeout=300)

        return success_response(data=data)


class MatchDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            match = Match.objects.get(id=pk)
        except Match.DoesNotExist:
            return error_response('Match not found', 404)

        # Check user is registered + approved
        from apps.tournaments.models import Registration
        reg = Registration.objects.filter(
            tournament=match.tournament,
            user=request.user,
            status='CONFIRMED',
        ).first()

        if not reg:
            return error_response('You are not registered for this tournament', 403)

        participant = MatchParticipant.objects.filter(
            match=match, user=request.user,
        ).first()

        data = MatchSerializer(match).data

        # ✅ Only approved participants see room
        if participant and participant.status == MatchParticipant.Status.APPROVED:
            data['my_participation'] = {
                'status': participant.status,
                'room_access_granted': participant.room_access_granted,
                'can_see_room': match.is_room_available,
            }

        return success_response(data=data)


class MatchRoomView(APIView):
    """
    Get room credentials — only:
    1. Registered + confirmed
    2. MatchParticipant APPROVED
    3. Current time >= room_release_time
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            match = Match.objects.get(id=pk)
        except Match.DoesNotExist:
            return error_response('Match not found', 404)

        # 1. Approved?
        participant = MatchParticipant.objects.filter(
            match=match, user=request.user,
        ).first()

        if not participant:
            return error_response('You are not a participant', 403)

        if participant.status != MatchParticipant.Status.APPROVED:
            return error_response(
                f'Your participation is {participant.status}. Contact admin.',
                403,
            )

        # 2. Time check
        if not match.is_room_available:
            mins_left = match.minutes_until_release
            return error_response(
                f'Room will be released in {mins_left} minutes',
                403,
                {
                    'minutes_left': mins_left,
                    'release_time': str(match.room_release_time),
                },
            )

        # 3. Room set?
        if not match.room_id:
            return error_response('Admin has not set room details yet', 404)

        # ✅ Grant room access
        if not participant.room_access_granted:
            participant.room_access_granted = True
            participant.save(update_fields=['room_access_granted'])

        return success_response(data={
            'room_id': match.room_id,
            'room_password': match.room_password,
            'room_notes': match.room_notes,
            'scheduled_start_time': str(match.scheduled_start_time),
            'minutes_until_start': match.minutes_until_start,
        })


# ==================================================
# ADMIN APIs
# ==================================================

class AdminMatchListCreateView(APIView):
    """Admin: list all matches + create new."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        tournament_id = request.query_params.get('tournament_id')
        status_filter = request.query_params.get('status')

        # ✅ Cache key
        cache_suffix = f'admin_{tournament_id or "all"}_{status_filter or "all"}'

        cached = get_cached_matches_list(cache_suffix)
        if cached is not None:
            return success_response(data=cached)

        qs = Match.objects.select_related('tournament').order_by('-scheduled_start_time')

        if tournament_id:
            qs = qs.filter(tournament_id=tournament_id)
        if status_filter and status_filter != 'ALL':
            qs = qs.filter(status=status_filter)

        data = []
        for m in qs:
            approved = m.participants.filter(
                status=MatchParticipant.Status.APPROVED
            ).count()
            pending = m.participants.filter(
                status=MatchParticipant.Status.PENDING
            ).count()
            rejected = m.participants.filter(
                status=MatchParticipant.Status.REJECTED
            ).count()

            data.append({
                'id': str(m.id),
                'tournament_id': str(m.tournament.id),
                'tournament_title': m.tournament.title,
                'tournament_display_id': m.tournament.display_id,
                'match_number': m.match_number,
                'title': m.title or f'Match {m.match_number}',
                'scheduled_start_time': str(m.scheduled_start_time),
                'room_release_time': str(m.room_release_time),
                'minutes_until_start': m.minutes_until_start,
                'is_room_available': m.is_room_available,
                'room_id': m.room_id,
                'room_password': m.room_password,
                'room_notes': m.room_notes,
                'max_participants': m.max_participants,
                'entry_fee': float(m.entry_fee),
                'status': m.status,
                'approved_count': approved,
                'pending_count': pending,
                'rejected_count': rejected,
                'total_participants': m.participants.count(),
                'created_at': str(m.created_at),
            })

        set_cached_matches_list(data, filters=cache_suffix, timeout=120)
        return success_response(data=data)

    def post(self, request):
        """Create match."""
        from apps.tournaments.models import Tournament

        tournament_id = request.data.get('tournament_id')
        match_number = request.data.get('match_number', 1)
        title = request.data.get('title', '')
        scheduled_start_time = request.data.get('scheduled_start_time')
        room_id = request.data.get('room_id', '')
        room_password = request.data.get('room_password', '')
        room_notes = request.data.get('room_notes', '')
        max_participants = request.data.get('max_participants', 50)
        entry_fee = request.data.get('entry_fee', 0)

        if not tournament_id:
            return error_response('tournament_id required', 400)
        if not scheduled_start_time:
            return error_response('scheduled_start_time required', 400)

        try:
            tournament = Tournament.objects.get(id=tournament_id)
        except Tournament.DoesNotExist:
            return error_response('Tournament not found', 404)

        scheduled_dt = parse_datetime(scheduled_start_time)
        if not scheduled_dt:
            return error_response('Invalid datetime format. Use ISO format.', 400)

        room_release = scheduled_dt - timedelta(minutes=5)

        if room_id and timezone.now() >= room_release:
            room_release = timezone.now() - timedelta(seconds=1)

        match = Match.objects.create(
            tournament=tournament,
            match_number=match_number,
            title=title,
            scheduled_start_time=scheduled_dt,
            room_release_time=room_release,
            room_id=room_id,
            room_password=room_password,
            room_notes=room_notes,
            max_participants=max_participants,
            entry_fee=entry_fee,
            created_by=request.user,
        )

        # ✅ Cache invalidate
        invalidate_match_cache(match.id)
        invalidate_match_cache()

        return success_response(
            data=MatchAdminSerializer(match).data,
            message=f'Match {match_number} created. Room will release at {room_release}.',
            status=201,
        )


class AdminMatchUpdateView(APIView):
    """Admin: update match — room, schedule, status."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        """Detail with participants."""
        try:
            match = Match.objects.get(id=pk)
        except Match.DoesNotExist:
            return error_response('Match not found', 404)

        participants = match.participants.select_related('user', 'registration')

        parts_data = []
        for p in participants:
            payment = None
            if p.registration:
                payment = p.registration.payments.order_by('-created_at').first()

            parts_data.append({
                'id': str(p.id),
                'user_id': str(p.user.id),
                'user_email': p.user_email or p.user.email,
                'user_mobile': p.user_mobile or getattr(p.user, 'mobile_number', ''),
                'user_upi_id': p.user_upi_id or getattr(p.user, 'upi_id', ''),
                'user_ff_uid': p.user_ff_uid,
                'user_ff_name': p.user_ff_name,
                'status': p.status,
                'room_access_granted': p.room_access_granted,
                'approved_at': str(p.approved_at) if p.approved_at else None,
                'rejection_reason': p.rejection_reason,
                'transaction_id': payment.transaction_id if payment else '',
                'payment_amount': float(payment.amount) if payment else 0,
                'payment_status': payment.status if payment else 'NO_PAYMENT',
                'payer_name': payment.payer_name if payment else '',
                'payer_upi_id': payment.payer_upi_id if payment else '',
                'payment_screenshot': payment.screenshot.url if payment and payment.screenshot else None,
                'created_at': str(p.created_at),
            })

        return success_response(data={
            'match': MatchAdminSerializer(match).data,
            'participants': parts_data,
            'total_participants': len(parts_data),
            'pending_count': participants.filter(status=MatchParticipant.Status.PENDING).count(),
            'approved_count': participants.filter(status=MatchParticipant.Status.APPROVED).count(),
            'rejected_count': participants.filter(status=MatchParticipant.Status.REJECTED).count(),
        })

    def patch(self, request, pk):
        """Update match."""
        try:
            match = Match.objects.get(id=pk)
        except Match.DoesNotExist:
            return error_response('Match not found', 404)

        if 'room_id' in request.data:
            match.room_id = request.data['room_id']
        if 'room_password' in request.data:
            match.room_password = request.data['room_password']
        if 'room_notes' in request.data:
            match.room_notes = request.data['room_notes']
        if 'title' in request.data:
            match.title = request.data['title']
        if 'status' in request.data:
            match.status = request.data['status']
        if 'scheduled_start_time' in request.data:
            dt = parse_datetime(request.data['scheduled_start_time'])
            if dt:
                match.scheduled_start_time = dt
                match.room_release_time = dt - timedelta(minutes=5)

        match.save()

        # ✅ Cache invalidate
        invalidate_match_cache(match.id)
        invalidate_match_cache()

        return success_response(
            data=MatchAdminSerializer(match).data,
            message='Match updated',
        )


class AdminMatchParticipantsView(APIView):
    """Admin: list participants of a match."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            match = Match.objects.get(id=pk)
        except Match.DoesNotExist:
            return error_response('Match not found', 404)

        participants = match.participants.select_related('user', 'registration')

        data = []
        for p in participants:
            payment = None
            if p.registration:
                payment = p.registration.payments.order_by('-created_at').first()

            data.append({
                'id': str(p.id),
                'user_id': str(p.user.id),
                'user_email': p.user_email or p.user.email,
                'user_mobile': p.user_mobile or getattr(p.user, 'mobile_number', ''),
                'user_upi_id': p.user_upi_id or getattr(p.user, 'upi_id', ''),
                'user_ff_uid': p.user_ff_uid,
                'user_ff_name': p.user_ff_name,
                'status': p.status,
                'room_access_granted': p.room_access_granted,
                'approved_at': str(p.approved_at) if p.approved_at else None,
                'rejection_reason': p.rejection_reason,
                'transaction_id': payment.transaction_id if payment else '',
                'payment_amount': float(payment.amount) if payment else 0,
                'payment_status': payment.status if payment else 'NO_PAYMENT',
                'payer_name': payment.payer_name if payment else '',
                'payer_upi_id': payment.payer_upi_id if payment else '',
                'payment_screenshot': payment.screenshot.url if payment and payment.screenshot else None,
                'created_at': str(p.created_at),
            })

        return success_response(data=data)


class AdminParticipantActionView(APIView):
    """
    Admin: Approve/Reject a participant.
    This is the CHECK button in admin panel.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk, participant_id):
        action = request.data.get('action')
        reason = request.data.get('reason', '')

        try:
            participant = MatchParticipant.objects.get(
                id=participant_id, match_id=pk,
            )
        except MatchParticipant.DoesNotExist:
            return error_response('Participant not found', 404)

        if action == 'approve':
            participant.status = MatchParticipant.Status.APPROVED
            participant.room_access_granted = True
            participant.approved_by = request.user
            participant.approved_at = timezone.now()
            participant.save()
        elif action == 'reject':
            participant.status = MatchParticipant.Status.REJECTED
            participant.room_access_granted = False
            participant.rejection_reason = reason
            participant.approved_by = request.user
            participant.approved_at = timezone.now()
            participant.save()
        else:
            return error_response('Invalid action. Use approve/reject', 400)

        # ✅ Cache invalidate
        invalidate_match_cache(pk)

        return success_response(
            data=MatchParticipantSerializer(participant).data,
            message=f'Participant {action}d',
        )