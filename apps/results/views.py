# apps/results/views.py

from datetime import timedelta
from decimal import Decimal
import re
import json
import difflib
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from firebase_admin import messaging

from apps.matches.models import Match
from apps.results.models import Result, PrizeConfig
from apps.results.services import ResultOCRService
from apps.results.utils.prize_calculator import (
    calculate_per_kill_prize,
    calculate_prize_amount,
    calculate_score,
)
from apps.tournaments.models import Registration
from apps.users.models import User
from apps.payments.models import UserNotification

# Cache Utilities
from apps.results.cache_utils import (
    invalidate_match_results_cache,
    warm_match_results_cache,
    get_cached_leaderboard,
    set_cached_leaderboard,
    get_cached_match_status,
    get_cached_admin_results,
    set_cached_admin_results,
    set_cached_match_status,
    get_cached_user_results,
    set_cached_user_results,
    get_cached_user_stats,
    set_cached_user_stats,
    get_cached_user_winnings,
    set_cached_user_winnings,
    get_cached_unread_count,
    set_cached_unread_count,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def get_cached_registrations(tournament):
    cache_key = f'registrations_v3_{tournament.id}'
    registrations = cache.get(cache_key)

    if registrations is None:
        qs = Registration.objects.filter(tournament=tournament).select_related('user')
        registrations = []
        for reg in qs:
            registrations.append({
                'user_id': reg.user.id,
                'user_email': reg.user.email,
                'user_display_name': reg.user.display_name,
                'user_mobile': reg.user.mobile_number,
                'user_upi': reg.user.upi_id,
                'ff_uid': reg.free_fire_uid or '',
                'ff_name': reg.free_fire_name or '',
            })
        cache.set(cache_key, registrations, timeout=600)

    return registrations


def soundex(word):
    if not word:
        return ''
    word = word.upper()
    codes = {'B': '1', 'F': '1', 'P': '1', 'V': '1',
             'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
             'D': '3', 'T': '3',
             'L': '4',
             'M': '5', 'N': '5',
             'R': '6'}
    first_letter = word[0]
    result = first_letter
    prev_code = codes.get(first_letter, '')
    for char in word[1:]:
        code = codes.get(char, '')
        if code and code != prev_code:
            result += code
        prev_code = code
    return (result + '000')[:4]


def match_players_waterfall(registrations, players_data):
    matched_results = {}
    locked_reg_ids = set()

    def clean_letters(s):
        return re.sub(r'[^a-z]', '', (s or '').lower())

    def clean_tokens(s):
        tokens = re.findall(r'[a-zA-Z]+', (s or '').lower())
        return ' '.join(sorted(tokens))

    # PASS 1: UID
    for p in players_data:
        rank = p.get('rank')
        ff_uid = str(p.get('ff_uid') or '').strip()
        if not rank or rank in matched_results or not ff_uid:
            continue
        for reg in registrations:
            if reg['user_id'] not in locked_reg_ids and reg['ff_uid'] == ff_uid:
                matched_results[rank] = reg
                locked_reg_ids.add(reg['user_id'])
                break

    # PASS 2: Exact Name
    for p in players_data:
        rank = p.get('rank')
        ocr_name = str(p.get('name') or '').strip()
        if not rank or rank in matched_results or not ocr_name:
            continue
        clean_ocr = clean_letters(ocr_name)
        if not clean_ocr:
            continue
        for reg in registrations:
            if reg['user_id'] in locked_reg_ids:
                continue
            clean_reg = clean_letters(reg['ff_name'])
            if clean_reg and clean_ocr == clean_reg:
                matched_results[rank] = reg
                locked_reg_ids.add(reg['user_id'])
                break

    # PASS 3: Cleaned Name (fuzzy 90%+)
    for p in players_data:
        rank = p.get('rank')
        ocr_name = str(p.get('name') or '').strip()
        if not rank or rank in matched_results or not ocr_name:
            continue
        clean_ocr = clean_letters(ocr_name)
        if not clean_ocr:
            continue
        best_match, best_score = None, 0.0
        for reg in registrations:
            if reg['user_id'] in locked_reg_ids:
                continue
            clean_reg = clean_letters(reg['ff_name'])
            if not clean_reg:
                continue
            sim = difflib.SequenceMatcher(None, clean_ocr, clean_reg).ratio()
            if sim > best_score:
                best_score = sim
                best_match = reg
        if best_score >= 0.9 and best_match:
            matched_results[rank] = best_match
            locked_reg_ids.add(best_match['user_id'])

    # PASS 4: Soundex
    for p in players_data:
        rank = p.get('rank')
        ocr_name = str(p.get('name') or '').strip()
        if not rank or rank in matched_results or not ocr_name:
            continue
        ocr_words = re.findall(r'[a-zA-Z]+', ocr_name.lower())
        if not ocr_words:
            continue
        ocr_soundex = [soundex(w) for w in ocr_words]
        best_match, best_overlap = None, 0
        for reg in registrations:
            if reg['user_id'] in locked_reg_ids:
                continue
            reg_words = re.findall(r'[a-zA-Z]+', (reg['ff_name'] or '').lower())
            if not reg_words:
                continue
            reg_soundex = [soundex(w) for w in reg_words]
            overlap = sum(1 for s in ocr_soundex if s in reg_soundex)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = reg
        if best_overlap >= 1 and best_match:
            if abs(len(ocr_name) - len(best_match['ff_name'])) <= 5:
                matched_results[rank] = best_match
                locked_reg_ids.add(best_match['user_id'])

    # PASS 5: Token Match
    for p in players_data:
        rank = p.get('rank')
        ocr_name = str(p.get('name') or '').strip()
        if not rank or rank in matched_results or not ocr_name:
            continue
        token_ocr = clean_tokens(ocr_name)
        if not token_ocr:
            continue
        best_match, best_score = None, 0.0
        for reg in registrations:
            if reg['user_id'] in locked_reg_ids:
                continue
            token_reg = clean_tokens(reg['ff_name'])
            if not token_reg:
                continue
            sim = difflib.SequenceMatcher(None, token_ocr, token_reg).ratio()
            if sim > best_score:
                best_score = sim
                best_match = reg
        if best_score >= 0.8 and best_match:
            matched_results[rank] = best_match
            locked_reg_ids.add(best_match['user_id'])

    # PASS 6: Fuzzy Match (60%+)
    for p in players_data:
        rank = p.get('rank')
        ocr_name = str(p.get('name') or '').strip()
        if not rank or rank in matched_results or not ocr_name:
            continue
        clean_ocr = clean_letters(ocr_name)
        if not clean_ocr:
            continue
        best_match, best_score = None, 0.0
        for reg in registrations:
            if reg['user_id'] in locked_reg_ids:
                continue
            clean_reg = clean_letters(reg['ff_name'])
            if not clean_reg:
                continue
            sim = difflib.SequenceMatcher(None, clean_ocr, clean_reg).ratio()
            if sim > best_score:
                best_score = sim
                best_match = reg
        if best_score >= 0.6 and best_match:
            matched_results[rank] = best_match
            locked_reg_ids.add(best_match['user_id'])

    # PASS 7: Length + Order
    remaining_players = [p for p in players_data if p.get('rank') and p['rank'] not in matched_results]
    remaining_regs = [reg for reg in registrations if reg['user_id'] not in locked_reg_ids]
    if len(remaining_players) == len(remaining_regs):
        remaining_players.sort(key=lambda x: x['rank'])
        remaining_regs.sort(key=lambda x: len(clean_letters(x['ff_name'])))
        for i, p in enumerate(remaining_players):
            rank = p['rank']
            ocr_name = str(p.get('name') or '').strip()
            reg = remaining_regs[i]
            if abs(len(clean_letters(ocr_name)) - len(clean_letters(reg['ff_name']))) <= 3:
                matched_results[rank] = reg
                locked_reg_ids.add(reg['user_id'])

    final_results = []
    for p in players_data:
        rank = p.get('rank')
        ocr_name = str(p.get('name') or '').strip()
        if rank and rank in matched_results:
            reg = matched_results[rank]
            final_results.append({
                'player_data': p,
                'matched_reg': reg,
                'matched_name': reg['ff_name'],
            })
        else:
            final_results.append({
                'player_data': p,
                'matched_reg': None,
                'matched_name': ocr_name,
            })
    return final_results


def send_fcm_notification(user, title, body, notif_type, screen, channel_id, sound_name, extra_data=None):
    """Generic FCM Sender to avoid repeating code"""
    if not user or not user.fcm_token:
        return
    try:
        data_payload = {
            'type': notif_type,
            'screen': screen,
        }
        if extra_data:
            data_payload.update(extra_data)

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data_payload,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id=channel_id,
                    sound=sound_name,
                ),
            ),
            token=user.fcm_token,
        )
        messaging.send(message)
        print(f"✅ FCM {notif_type} sent to {user.email}")
    except Exception as e:
        print(f"❌ FCM error: {e}")


# ═══════════════════════════════════════════════════════════
# ADMIN VIEWS
# ═══════════════════════════════════════════════════════════

class AdminResultUploadView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @transaction.atomic
    def post(self, request):
        match_id = request.data.get('match_id')
        players_data_str = request.data.get('players_data')
        file = request.FILES.get('screenshot')

        if not match_id:
            return Response({'success': False, 'error': {'message': 'match_id required'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            match = Match.objects.select_related('tournament').get(id=match_id)
        except Match.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Match not found'}}, status=status.HTTP_404_NOT_FOUND)

        tournament = match.tournament
        entry_fee = tournament.entry_fee
        per_kill = calculate_per_kill_prize(entry_fee)

        # ─── CASE 1: MULTI-PLAYER LIST ───
        if players_data_str:
            try:
                players_data = json.loads(players_data_str)
                if not isinstance(players_data, list):
                    raise ValueError("Must be a list")
            except Exception as e:
                return Response({'success': False, 'error': {'message': f'Invalid players_data: {e}'}}, status=status.HTTP_400_BAD_REQUEST)

            registrations = get_cached_registrations(tournament)
            matched_list = match_players_waterfall(registrations, players_data)

            results_created = []
            users_matched = 0
            total_prize = Decimal('0.00')
            affected_user_ids = []

            for item in matched_list:
                p = item['player_data']
                reg = item['matched_reg']
                matched_name = item['matched_name']

                kills = int(p.get('kills', 0) or 0)
                rank = int(p.get('rank', 0) or 0)
                placement = rank if rank > 0 else 99
                ocr_name = p.get('name') or ''

                prize = calculate_prize_amount(entry_fee, kills)
                score = calculate_score(kills, placement)
                points = Result.calculate_points(entry_fee, kills)
                total_prize += prize

                if reg:
                    users_matched += 1
                    user_obj = User.objects.filter(id=reg['user_id']).first()
                    if user_obj:
                        affected_user_ids.append(user_obj.id)
                else:
                    user_obj = None

                final_name = matched_name if matched_name else ocr_name

                if user_obj:
                    Result.objects.update_or_create(
                        match=match, user=user_obj,
                        defaults={
                            'free_fire_uid': p.get('ff_uid') or '',
                            'player_name': final_name,
                            'kills': kills,
                            'placement': placement,
                            'score': score,
                            'prize_amount': prize,
                            'per_kill_prize': per_kill,
                            'entry_fee': entry_fee,
                            'points_earned': points,
                            'verification_status': Result.VerificationStatus.PENDING,
                        },
                    )
                    
                    # DB Notification
                    UserNotification.objects.create(
                        user=user_obj, type='result_published',
                        title='🏆 Result Announced!',
                        message=(f'Aapka result aa gaya!\n\nKills: {kills}\nPlacement: #{placement}\nPrize: ₹{prize}'),
                    )
                    
                    # FCM Notification
                    send_fcm_notification(
                        user=user_obj,
                        title='🏆 Result Announced!',
                        body=f'Kills: {kills}, Prize: ₹{prize}',
                        notif_type='result_published',
                        screen='result',
                        channel_id='result_channel_v2',
                        sound_name='result',
                        extra_data={'match_id': str(match.id)}
                    )
                    
                else:
                    Result.objects.create(
                        match=match, user=None,
                        free_fire_uid=p.get('ff_uid') or '',
                        player_name=final_name,
                        kills=kills, placement=placement,
                        score=score, prize_amount=prize,
                        per_kill_prize=per_kill, entry_fee=entry_fee,
                        points_earned=points,
                        verification_status=Result.VerificationStatus.PENDING,
                    )

                user_data = None
                if reg:
                    user_data = {
                        'id': str(reg['user_id']),
                        'email': reg['user_email'],
                        'display_name': reg['user_display_name'],
                        'mobile_number': reg['user_mobile'],
                        'upi_id': reg['user_upi'],
                        'free_fire_uid': reg['ff_uid'],
                        'free_fire_name': reg['ff_name'],
                    }

                results_created.append({
                    'rank': rank,
                    'ocr_name': ocr_name,
                    'matched_name': final_name,
                    'kills': kills,
                    'prize_amount': float(prize),
                    'matched_user': user_data,
                })

            invalidate_match_results_cache(match_id=match.id, user_ids=affected_user_ids)

            return Response({
                'success': True,
                'message': f'{len(results_created)} results saved. {users_matched} matched.',
                'data': {
                    'total_extracted': len(results_created),
                    'users_matched': users_matched,
                    'total_prize_pool': float(total_prize),
                    'per_kill_prize': float(per_kill),
                    'results': results_created,
                }
            }, status=status.HTTP_201_CREATED)

        # ─── CASE 2: SINGLE SCREENSHOT ───
        if not file:
            return Response({'success': False, 'error': {'message': 'screenshot or players_data required'}}, status=status.HTTP_400_BAD_REQUEST)

        image_bytes = file.read()
        file.seek(0)

        ocr_result = ResultOCRService.extract_result_info(image_bytes)
        data = ocr_result.get('data', {})

        kills = int(data.get('kills', 0) or 0)
        placement = int(data.get('placement', 0) or 0)

        prize = calculate_prize_amount(entry_fee, kills)
        score = calculate_score(kills, placement)
        points = Result.calculate_points(entry_fee, kills)

        registrations = get_cached_registrations(tournament)
        matched_list = match_players_waterfall(registrations, [{
            'ff_uid': data.get('free_fire_uid'),
            'name': data.get('player_name'),
        }])

        reg = matched_list[0]['matched_reg'] if matched_list else None
        matched_name = matched_list[0]['matched_name'] if matched_list else data.get('player_name', '')

        user_data = None
        user_obj = None
        if reg:
            user_obj = User.objects.filter(id=reg['user_id']).first()
            if user_obj:
                user_data = {
                    'id': str(user_obj.id),
                    'email': user_obj.email,
                    'display_name': user_obj.display_name,
                    'mobile_number': user_obj.mobile_number,
                    'upi_id': user_obj.upi_id,
                    'free_fire_uid': user_obj.free_fire_uid,
                    'free_fire_name': user_obj.free_fire_name,
                }

        result_obj = Result.objects.create(
            match=match, user=user_obj,
            free_fire_uid=data.get('free_fire_uid', ''),
            player_name=matched_name or data.get('player_name', ''),
            kills=kills, placement=placement,
            score=score, prize_amount=prize,
            per_kill_prize=per_kill, entry_fee=entry_fee,
            points_earned=points,
            screenshot=file,
            ocr_raw_text=ocr_result.get('raw_text', ''),
            ocr_confidence=ocr_result.get('confidence', 0.0),
        )
        
        if user_obj:
            UserNotification.objects.create(
                user=user_obj, type='result_published',
                title='🏆 Result Announced!',
                message=(f'Aapka result aa gaya!\n\nKills: {kills}\nPlacement: #{placement}\nPrize: ₹{prize}'),
            )
            send_fcm_notification(
                user=user_obj,
                title='🏆 Result Announced!',
                body=f'Kills: {kills}, Prize: ₹{prize}',
                notif_type='result_published',
                screen='result',
                channel_id='result_channel_v2',
                sound_name='result',
                extra_data={'match_id': str(match.id)}
            )

        invalidate_match_results_cache(match_id=match.id, user_ids=[user_obj.id] if user_obj else [])

        return Response({
            'success': True,
            'message': 'Result uploaded',
            'data': {
                'id': str(result_obj.id),
                'player_name': result_obj.player_name,
                'kills': kills,
                'placement': placement,
                'score': score,
                'prize_amount': float(prize),
                'per_kill_prize': float(per_kill),
                'entry_fee': float(entry_fee),
                'points_earned': points,
                'free_fire_uid': result_obj.free_fire_uid,
                'user_matched': bool(user_obj),
                'user': user_data,
            }
        }, status=status.HTTP_201_CREATED)


class AdminAddResultView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, match_id):
        try:
            match = Match.objects.select_related('tournament').get(id=match_id)
        except Match.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Match not found'}}, status=status.HTTP_404_NOT_FOUND)

        user_email = request.data.get('user_email', '').strip().lower()
        if not user_email:
            return Response({'success': False, 'error': {'message': 'user_email required'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'User not found'}}, status=status.HTTP_404_NOT_FOUND)

        kills = int(request.data.get('kills', 0) or 0)
        placement = int(request.data.get('placement', 0) or 0)

        entry_fee = match.tournament.entry_fee
        per_kill = calculate_per_kill_prize(entry_fee)
        prize = calculate_prize_amount(entry_fee, kills)
        score = calculate_score(kills, placement)
        points = Result.calculate_points(entry_fee, kills)

        result, created = Result.objects.update_or_create(
            match=match, user=user,
            defaults={
                'kills': kills, 'placement': placement,
                'score': score, 'prize_amount': prize,
                'per_kill_prize': per_kill, 'entry_fee': entry_fee,
                'points_earned': points,
                'free_fire_uid': request.data.get('free_fire_uid', user.free_fire_uid or ''),
                'player_name': request.data.get('player_name', user.free_fire_name or user.display_name or ''),
                'verification_status': Result.VerificationStatus.PUBLISHED,
                'published_at': timezone.now(),
            },
        )

        UserNotification.objects.create(
            user=user, type='result_published',
            title='🏆 Result Announced!',
            message=(f'Aapka result aa gaya!\n\nKills: {kills}\nPlacement: #{placement}\nPrize: ₹{prize}'),
        )
        send_fcm_notification(
            user=user,
            title='🏆 Result Announced!',
            body=f'Kills: {kills}, Prize: ₹{prize}',
            notif_type='result_published',
            screen='result',
            channel_id='result_channel_v2',
            sound_name='result',
            extra_data={'match_id': str(match.id)}
        )

        invalidate_match_results_cache(match_id=match.id, user_ids=[user.id])

        return Response({
            'success': True,
            'message': 'Result added' if created else 'Result updated',
            'data': {
                'id': str(result.id),
                'kills': kills, 'placement': placement,
                'score': score, 'prize_amount': float(prize),
                'per_kill_prize': float(per_kill),
                'entry_fee': float(entry_fee),
                'points_earned': points,
            }
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class AdminResultListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, match_id):
        cached = get_cached_admin_results(match_id)
        if cached is not None:
            return Response({'success': True, 'data': cached})

        try:
            match = Match.objects.select_related('tournament').get(id=match_id)
        except Match.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Match not found'}}, status=status.HTTP_404_NOT_FOUND)

        registered_user_ids = set(
            Registration.objects.filter(tournament=match.tournament).values_list('user_id', flat=True)
        )

        results = Result.objects.filter(
            match_id=match_id, user_id__in=registered_user_ids,
        ).select_related('user').order_by('-score', '-kills')

        entry_fee = match.tournament.entry_fee if match.tournament else 0
        per_kill = calculate_per_kill_prize(entry_fee)

        data = []
        for rank, r in enumerate(results, start=1):
            user = r.user
            data.append({
                'id': str(r.id), 'rank': rank, 'player_name': r.player_name,
                'kills': r.kills, 'placement': r.placement, 'score': r.score,
                'prize_amount': float(r.prize_amount),
                'per_kill_prize': float(r.per_kill_prize or 0),
                'points_earned': r.points_earned,
                'verification_status': r.verification_status,
                'is_paid': getattr(r, 'is_paid', False),
                'free_fire_uid': r.free_fire_uid,
                'user_id': str(user.id) if user else None,
                'user_email': user.email if user else None,
                'user_mobile': user.mobile_number if user else None,
                'user_upi_id': user.upi_id if user else None,
                'user_ff_uid': user.free_fire_uid if user else None,
                'user_ff_name': user.free_fire_name if user else None,
                'user_display_name': user.display_name if user else None,
                'screenshot_url': (request.build_absolute_uri(r.screenshot.url) if r.screenshot else None),
            })

        response_data = {
            'match_id': str(match.id),
            'match_title': match.title,
            'tournament_title': match.tournament.title if match.tournament else '',
            'total': len(data),
            'entry_fee': float(entry_fee),
            'per_kill_prize': float(per_kill),
            'total_registered': len(registered_user_ids),
            'results': data,
        }

        set_cached_admin_results(match_id, response_data, timeout=120)
        return Response({'success': True, 'data': response_data})


class AdminResultPublishView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, match_id):
        try:
            match = Match.objects.select_related('tournament').get(id=match_id)
        except Match.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Match not found'}}, status=status.HTTP_404_NOT_FOUND)

        results = Result.objects.filter(match_id=match_id).select_related('user')
        count = results.update(
            verification_status=Result.VerificationStatus.PUBLISHED,
            published_at=timezone.now(),
        )

        match.status = 'COMPLETED'
        match.save(update_fields=['status'])

        tournament = match.tournament
        all_matches = Match.objects.filter(tournament=tournament)
        completed_matches = all_matches.filter(status='COMPLETED')

        tournament_completed = False
        if all_matches.count() > 0 and all_matches.count() == completed_matches.count():
            tournament.status = 'COMPLETED'
            tournament.save(update_fields=['status'])
            tournament_completed = True

        from apps.users.services.referral_service import ReferralService

        for r in results:
            if not r.user:
                continue
            try:
                reward = ReferralService.check_and_grant_referral_reward(r.user)
                if reward.get('free_entry_granted'):
                    print(f"🎁 Referral reward granted to {reward['referrer'].email}")
            except Exception as e:
                print(f"⚠️ Referral reward error: {e}")

        for r in results:
            if not r.user:
                continue
            points = Result.calculate_points(r.entry_fee, r.kills)
            if points > 0:
                r.points_earned = points
                r.save(update_fields=['points_earned'])
                r.user.add_points(points)
                try:
                    UserNotification.objects.create(
                        user=r.user, type='points_earned',
                        title=f'💎 +{points} Kuberaa Points!',
                        message=(f'Aapko {points} Points mile!\n\nKills: {r.kills}\nMatch: {r.match.title if r.match else "Match"}\n\nTotal: {r.user.kuberaa_points}'),
                    )
                except Exception as e:
                    print(f'⚠️ Points notification failed: {e}')

            if not r.user.has_played_first_match:
                r.user.has_played_first_match = True
                r.user.save(update_fields=['has_played_first_match'])

            if tournament_completed:
                UserNotification.objects.create(
                    user=r.user, type='tournament_completed',
                    title='🎉 Tournament Complete!',
                    message=(f'{tournament.title} khatam ho gaya!\n\nAapka final prize: ₹{r.prize_amount}'),
                )

        affected_user_ids = [r.user.id for r in results if r.user]
        invalidate_match_results_cache(match_id=match.id, user_ids=affected_user_ids)

        leaderboard_data = []
        published_results = Result.objects.filter(
            match_id=match.id, verification_status=Result.VerificationStatus.PUBLISHED,
        ).order_by('-score', '-kills')

        for rank, r in enumerate(published_results, start=1):
            leaderboard_data.append({
                'rank': rank, 'player_name': r.player_name, 'kills': r.kills,
                'placement': r.placement, 'score': r.score,
                'prize_amount': float(r.prize_amount), 'is_me': False,
            })

        warm_match_results_cache(match.id, leaderboard_data)

        return Response({
            'success': True,
            'message': f'{count} results published',
            'data': {
                'results_published': count,
                'match_status': match.status,
                'tournament_status': tournament.status,
                'tournament_completed': tournament_completed,
                'total_matches': all_matches.count(),
                'completed_matches': completed_matches.count(),
            }
        })


class AdminPrizeConfigView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, tournament_id):
        from apps.tournaments.models import Tournament
        try:
            tournament = Tournament.objects.get(id=tournament_id)
        except Tournament.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Tournament not found'}}, status=status.HTTP_404_NOT_FOUND)

        config, _ = PrizeConfig.objects.get_or_create(tournament=tournament)
        config.per_kill_amount = request.data.get('per_kill_amount', config.per_kill_amount)
        config.first_place_bonus = request.data.get('first_place_bonus', config.first_place_bonus)
        config.second_place_bonus = request.data.get('second_place_bonus', config.second_place_bonus)
        config.third_place_bonus = request.data.get('third_place_bonus', config.third_place_bonus)
        config.save()

        return Response({
            'success': True,
            'data': {
                'per_kill_amount': float(config.per_kill_amount),
                'first_place_bonus': float(config.first_place_bonus),
                'second_place_bonus': float(config.second_place_bonus),
                'third_place_bonus': float(config.third_place_bonus),
            },
            'message': 'Prize config updated',
        })


class AdminMarkPrizePaidView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, result_id):
        try:
            result = Result.objects.select_for_update().select_related('user', 'match', 'match__tournament').get(id=result_id)
        except Result.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Result not found'}}, status=status.HTTP_404_NOT_FOUND)

        if getattr(result, 'is_paid', False):
            return Response({'success': False, 'error': {'message': 'Already marked paid'}}, status=status.HTTP_400_BAD_REQUEST)

        result.is_paid = True
        result.paid_at = timezone.now()
        result.save()

        if result.user:
            kills = result.kills or 0
            prize = float(result.prize_amount or 0)
            per_kill = float(result.per_kill_prize or 0)

            UserNotification.objects.create(
                user=result.user, type='prize_paid',
                title=f'🎉 You Won ₹{prize:.0f}!',
                message=(f'Mubarak ho!\n\n🏆 {result.match.tournament.title if result.match and result.match.tournament else "Tournament"}\n🎮 {result.match.title if result.match else "Match"}\n💀 Kills: {kills} × ₹{per_kill:.1f} = ₹{prize:.2f}\n📊 Placement: #{result.placement}\n🏅 Score: {result.score}\n\n💰 Aapka total winnings check karo!'),
            )
            
            send_fcm_notification(
                user=result.user,
                title=f'🎉 You Won ₹{prize:.0f}!',
                body=f'Kills: {kills}, Placement: #{result.placement}',
                notif_type='prize_paid',
                screen='result',
                channel_id='winning_channel_v2', # Winning Channel
                sound_name='winning',            # Winning Sound
                extra_data={'prize_amount': str(prize)}
            )

        invalidate_match_results_cache(match_id=result.match.id, user_ids=[result.user.id] if result.user else [])

        return Response({
            'success': True,
            'message': f'Prize ₹{result.prize_amount} marked as paid',
            'data': {
                'id': str(result.id),
                'is_paid': True,
                'paid_at': result.paid_at.isoformat(),
                'user_email': result.user.email if result.user else None,
                'user_mobile': result.user.mobile_number if result.user else None,
                'user_upi_id': result.user.upi_id if result.user else None,
                'kills': result.kills,
                'prize_amount': float(result.prize_amount),
                'points_earned': result.points_earned,
            }
        })


# ═══════════════════════════════════════════════════════════
# USER VIEWS
# ═══════════════════════════════════════════════════════════

class UserStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user_id = request.user.id
        cached = get_cached_user_stats(user_id)
        if cached is not None:
            return Response({'success': True, 'data': cached})

        results = Result.objects.filter(user=request.user, verification_status=Result.VerificationStatus.PUBLISHED)
        data = {
            'total_winnings': sum(float(r.prize_amount or 0) for r in results),
            'total_kills': sum(r.kills or 0 for r in results),
            'total_matches': results.count(),
            'total_wins': results.filter(placement=1).count(),
        }
        set_cached_user_stats(user_id, data, timeout=600)
        return Response({'success': True, 'data': data})


class UserMyResultsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user_id = request.user.id
        cached = get_cached_user_results(user_id)
        if cached is not None:
            return Response({'success': True, 'data': cached})

        results = Result.objects.filter(
            user=request.user, verification_status=Result.VerificationStatus.PUBLISHED,
        ).select_related('match', 'match__tournament').order_by('-created_at')

        data = []
        for r in results:
            data.append({
                'id': str(r.id),
                'match_id': str(r.match.id) if r.match else None,
                'match_title': r.match.title if r.match else 'Match',
                'match_status': r.match.status if r.match else 'UNKNOWN',
                'tournament_title': r.match.tournament.title if r.match and r.match.tournament else '',
                'player_name': r.player_name, 'kills': r.kills,
                'placement': r.placement, 'score': r.score,
                'prize_amount': float(r.prize_amount),
                'per_kill_prize': float(r.per_kill_prize or 0),
                'points_earned': r.points_earned, 'is_paid': r.is_paid,
                'free_fire_uid': r.free_fire_uid,
                'created_at': r.created_at.isoformat(),
                'published_at': r.published_at.isoformat() if r.published_at else None,
            })

        response_data = {
            'total_matches': results.count(),
            'total_winnings': sum(float(r.prize_amount or 0) for r in results),
            'total_kills': sum(r.kills or 0 for r in results),
            'total_wins': results.filter(placement=1).count(),
            'results': data,
        }
        set_cached_user_results(user_id, response_data, timeout=300)
        return Response({'success': True, 'data': response_data})


class UserWinningsSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user_id = request.user.id
        cached = get_cached_user_winnings(user_id)
        if cached is not None:
            return Response({'success': True, 'data': cached})

        user = request.user
        paid_results = Result.objects.filter(user=user, is_paid=True).select_related('match', 'match__tournament').order_by('-paid_at')
        pending_results = Result.objects.filter(user=user, is_paid=False, verification_status=Result.VerificationStatus.PUBLISHED)

        matches = []
        for r in paid_results:
            matches.append({
                'id': str(r.id),
                'match_title': r.match.title if r.match else 'Match',
                'tournament_title': r.match.tournament.title if r.match and r.match.tournament else '',
                'kills': r.kills, 'placement': r.placement, 'score': r.score,
                'prize_amount': float(r.prize_amount),
                'per_kill_prize': float(r.per_kill_prize or 0),
                'is_paid': True, 'paid_at': r.paid_at.isoformat() if r.paid_at else None,
            })

        data = {
            'total_won': sum(float(r.prize_amount or 0) for r in paid_results),
            'pending_amount': sum(float(r.prize_amount or 0) for r in pending_results),
            'total_kills': sum(r.kills or 0 for r in paid_results),
            'total_matches': paid_results.count(),
            'total_wins': paid_results.filter(placement=1).count(),
            'matches': matches,
        }
        set_cached_user_winnings(user_id, data, timeout=300)
        return Response({'success': True, 'data': data})


class UnreadResultsCountView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user_id = request.user.id
        cached = get_cached_unread_count(user_id)
        if cached is not None:
            return Response({'success': True, 'data': {'count': cached}})

        cutoff = timezone.now() - timedelta(days=7)
        count = Result.objects.filter(
            user=request.user, verification_status=Result.VerificationStatus.PUBLISHED, created_at__gte=cutoff
        ).count()

        set_cached_unread_count(user_id, count, timeout=120)
        return Response({'success': True, 'data': {'count': count}})


class UserResultListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, match_id):
        cached = get_cached_leaderboard(match_id)

        if cached is not None:
            user_player_names = set(
                Result.objects.filter(match_id=match_id, user=request.user, verification_status=Result.VerificationStatus.PUBLISHED).values_list('player_name', flat=True)
            )
            data = []
            for item in cached:
                item_copy = dict(item)
                item_copy['is_me'] = item.get('player_name') in user_player_names
                data.append(item_copy)
            return Response({'success': True, 'data': data})

        results = Result.objects.filter(match_id=match_id, verification_status=Result.VerificationStatus.PUBLISHED).order_by('-score', '-kills')
        data, generic = [], []
        for rank, r in enumerate(results, start=1):
            item = {'rank': rank, 'player_name': r.player_name, 'kills': r.kills, 'placement': r.placement, 'score': r.score, 'prize_amount': float(r.prize_amount)}
            data.append({**item, 'is_me': r.user_id == request.user.id})
            generic.append({**item, 'is_me': False})

        set_cached_leaderboard(match_id, generic, timeout=300)
        return Response({'success': True, 'data': data})


class UserMatchStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, match_id):
        user_id = request.user.id
        cached = get_cached_match_status(match_id, user_id)
        if cached is not None:
            return Response({'success': True, 'data': cached})

        try:
            match = Match.objects.select_related('tournament').get(id=match_id)
        except Match.DoesNotExist:
            return Response({'success': False, 'error': {'message': 'Match not found'}}, status=status.HTTP_404_NOT_FOUND)

        my_result = Result.objects.filter(match=match, user=request.user, verification_status=Result.VerificationStatus.PUBLISHED).first()
        data = {
            'match_id': str(match.id), 'match_title': match.title, 'match_status': match.status,
            'is_completed': match.status == 'COMPLETED', 'tournament_title': match.tournament.title,
            'tournament_status': match.tournament.status,
            'my_result': {'id': str(my_result.id), 'kills': my_result.kills, 'placement': my_result.placement, 'score': my_result.score, 'prize_amount': float(my_result.prize_amount), 'points_earned': my_result.points_earned, 'is_paid': my_result.is_paid} if my_result else None,
        }
        set_cached_match_status(match_id, user_id, data, timeout=180)
        return Response({'success': True, 'data': data})


class WithdrawalHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        cache_key = f'results_withdrawals_{request.user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({'success': True, 'data': cached})

        results = Result.objects.filter(user=request.user, is_paid=True).select_related('match', 'match__tournament').order_by('-paid_at')
        data = []
        total_paid = 0
        for r in results:
            amount = float(r.prize_amount or 0)
            total_paid += amount
            data.append({'id': str(r.id), 'match_title': r.match.title if r.match else 'Match', 'tournament_title': r.match.tournament.title if r.match and r.match.tournament else '', 'amount': amount, 'upi_id': request.user.upi_id, 'paid_at': r.paid_at.isoformat() if r.paid_at else None})

        response_data = {'total_paid': total_paid, 'total_withdrawals': len(data), 'withdrawals': data}
        cache.set(cache_key, response_data, timeout=300)
        return Response({'success': True, 'data': response_data})