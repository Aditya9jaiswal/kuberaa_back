# apps/leaderboard/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from apps.results.models import Result
from core.responses import success_response


class WeeklyLeaderboardView(APIView):
    def get(self, request):
        # ✅ Cache 5 min
        cache_key = 'leaderboard_weekly'
        cached = cache.get(cache_key)
        if cached is not None:
            return success_response(data=cached)

        last_week = timezone.now() - timedelta(days=7)

        # ✅ Only published results
        top_players = Result.objects.filter(
            created_at__gte=last_week,
            user__isnull=False,
            verification_status=Result.VerificationStatus.PUBLISHED,
        ).values(
            'user__id',
            'user__display_name',
            'user__email',
        ).annotate(
            total_kills=Sum('kills'),
            total_matches=Count('id'),
        ).order_by('-total_kills')[:10]

        data = [
            {
                'rank': idx + 1,
                'user_id': str(p['user__id']),
                'name': (
                    p['user__display_name']
                    or p['user__email'].split('@')[0]
                ),
                'email': p['user__email'],
                'total_kills': p['total_kills'] or 0,
                'total_matches': p['total_matches'] or 0,
            }
            for idx, p in enumerate(top_players)
        ]

        # ✅ Cache 5 min
        cache.set(cache_key, data, timeout=300)

        return success_response(data=data)


class MatchLeaderboardView(APIView):
    """Match-specific leaderboard (top 10 by score)"""
    def get(self, request, match_id):
        # ✅ Cache 5 min
        cache_key = f'leaderboard_match_{match_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return success_response(data=cached)

        results = Result.objects.filter(
            match_id=match_id,
            verification_status=Result.VerificationStatus.PUBLISHED,
        ).order_by('-score', '-kills')[:10]

        data = [
            {
                'rank': idx + 1,
                'player_name': r.player_name,
                'kills': r.kills,
                'placement': r.placement,
                'score': r.score,
                'prize_amount': float(r.prize_amount),
            }
            for idx, r in enumerate(results)
        ]

        # ✅ Cache 5 min
        cache.set(cache_key, data, timeout=300)

        return success_response(data=data)