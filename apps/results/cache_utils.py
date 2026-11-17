# apps/results/cache_utils.py

from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# KEY BUILDERS
# ═══════════════════════════════════════════════════════════

def _leaderboard_key(match_id):
    return f'results_leaderboard_{match_id}'


def _admin_results_key(match_id):
    return f'admin_results_{match_id}'


def _match_status_key(match_id, user_id):
    return f'results_match_status_{match_id}_user_{user_id}'


def _user_results_key(user_id):
    return f'results_user_my_{user_id}'


def _user_stats_key(user_id):
    return f'results_user_stats_{user_id}'


def _user_winnings_key(user_id):
    return f'results_user_winnings_{user_id}'


def _unread_count_key(user_id):
    return f'results_unread_count_{user_id}'


def _user_notifications_key(user_id):
    return f'user_notifications_{user_id}'


def _unread_notifications_key(user_id):
    return f'user_notifications_unread_{user_id}'


def _tournaments_list_key(filters='all'):
    return f'tournaments_list_{filters}'


def _tournament_detail_key(tournament_id):
    return f'tournament_detail_{tournament_id}'


def _matches_list_key(filters='all'):
    return f'matches_list_{filters}'


def _match_detail_key(match_id):
    return f'match_detail_{match_id}'


def _tournament_registrations_key(tournament_id):
    return f'tournament_registrations_{tournament_id}'


def _users_list_key(filters='all'):
    return f'users_list_{filters}'


def _user_detail_key(user_id):
    return f'user_detail_{user_id}'


# ═══════════════════════════════════════════════════════════
# INVALIDATE — admin action ke baad
# ═══════════════════════════════════════════════════════════

def invalidate_match_results_cache(match_id, user_ids=None):
    """Result upload/publish/mark-paid ke baad"""
    try:
        cache.delete(_leaderboard_key(match_id))
        cache.delete(_admin_results_key(match_id))
        logger.info(f'🗑️  Cache invalidated: leaderboard + admin_{match_id}')

        if user_ids:
            for uid in user_ids:
                cache.delete(_match_status_key(match_id, uid))
                cache.delete(_user_results_key(uid))
                cache.delete(_user_stats_key(uid))
                cache.delete(_user_winnings_key(uid))
                cache.delete(_unread_count_key(uid))
                # ✅ Notifications bhi clear
                invalidate_notifications_cache(uid)
            logger.info(f'🗑️  User caches invalidated: {len(user_ids)} users')
    except Exception as e:
        logger.exception(f'⚠️  Cache invalidation error: {e}')


def invalidate_tournament_cache(tournament_id=None):
    """Tournament create/update/delete ke baad"""
    try:
        if tournament_id:
            cache.delete(_tournament_detail_key(tournament_id))
            cache.delete(_tournament_registrations_key(tournament_id))
        
        for page in ['1', '2', '3', '4', '5']:
            cache.delete(_tournaments_list_key(f'page_{page}'))
        
        for f in ['all', 'OPEN', 'LIVE', 'COMPLETED', 'DRAFT']:
            cache.delete(_tournaments_list_key(f))
        
        logger.info(f'🗑️  Tournament cache invalidated: {tournament_id or "ALL"}')
    except Exception as e:
        logger.exception(f'⚠️  Error: {e}')


def invalidate_match_cache(match_id=None):
    """Match create/update/delete ke baad"""
    try:
        if match_id:
            cache.delete(_match_detail_key(match_id))
        
        for page in ['1', '2', '3', '4', '5']:
            cache.delete(_matches_list_key(f'page_{page}'))
        
        for f in ['all', 'SCHEDULED', 'LIVE', 'COMPLETED', 'CANCELLED']:
            cache.delete(_matches_list_key(f))
        
        logger.info(f'🗑️  Match cache invalidated: {match_id or "ALL"}')
    except Exception as e:
        logger.exception(f'⚠️  Error: {e}')


def invalidate_user_cache(user_id=None):
    """User update/block ke baad"""
    try:
        if user_id:
            cache.delete(_user_detail_key(user_id))
            cache.delete(_user_results_key(user_id))
            cache.delete(_user_stats_key(user_id))
            cache.delete(_user_winnings_key(user_id))
        for f in ['all', 'ACTIVE', 'BLOCKED']:
            cache.delete(_users_list_key(f))
        logger.info(f'🗑️  User cache invalidated: {user_id or "ALL"}')
    except Exception as e:
        logger.exception(f'⚠️  Error: {e}')


def invalidate_notifications_cache(user_id):
    """Notification create/read ke baad — sab filter suffixes clear karo"""
    try:
        # Base keys
        cache.delete(_user_notifications_key(user_id))
        cache.delete(_unread_notifications_key(user_id))
        
        # ✅ Saare filter suffixes clear
        suffixes = [
            'all_all', 'all_unread',
            'result_published_all', 'result_published_unread',
            'prize_paid_all', 'prize_paid_unread',
            'points_earned_all', 'tournament_completed_all',
            'payment_verified_all', 'payment_rejected_all',
            'account_blocked_all',
            'payments_all', 'payments_unread',
        ]
        for s in suffixes:
            cache.delete(f'{_user_notifications_key(user_id)}_{s}')
        
        logger.info(f'🗑️  Notifications invalidated: user_{user_id}')
    except Exception as e:
        logger.exception(f'⚠️  Error: {e}')


# ═══════════════════════════════════════════════════════════
# WARM
# ═══════════════════════════════════════════════════════════

def warm_match_results_cache(match_id, results_list, timeout=300):
    try:
        cache.set(_leaderboard_key(match_id), results_list, timeout=timeout)
        logger.info(f'🔥 Cache warmed: leaderboard_{match_id}')
    except Exception as e:
        logger.exception(f'⚠️  Cache warm error: {e}')


# ═══════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════

def get_cached_leaderboard(match_id):
    return cache.get(_leaderboard_key(match_id))


def set_cached_leaderboard(match_id, data, timeout=300):
    cache.set(_leaderboard_key(match_id), data, timeout=timeout)


def get_cached_admin_results(match_id):
    return cache.get(_admin_results_key(match_id))


def set_cached_admin_results(match_id, data, timeout=120):
    cache.set(_admin_results_key(match_id), data, timeout=timeout)


def get_cached_match_status(match_id, user_id):
    return cache.get(_match_status_key(match_id, user_id))


def set_cached_match_status(match_id, user_id, data, timeout=180):
    cache.set(_match_status_key(match_id, user_id), data, timeout=timeout)


def get_cached_user_results(user_id):
    return cache.get(_user_results_key(user_id))


def set_cached_user_results(user_id, data, timeout=300):
    cache.set(_user_results_key(user_id), data, timeout=timeout)


def get_cached_user_stats(user_id):
    return cache.get(_user_stats_key(user_id))


def set_cached_user_stats(user_id, data, timeout=600):
    cache.set(_user_stats_key(user_id), data, timeout=timeout)


def get_cached_user_winnings(user_id):
    return cache.get(_user_winnings_key(user_id))


def set_cached_user_winnings(user_id, data, timeout=300):
    cache.set(_user_winnings_key(user_id), data, timeout=timeout)


def get_cached_unread_count(user_id):
    return cache.get(_unread_count_key(user_id))


def set_cached_unread_count(user_id, count, timeout=120):
    cache.set(_unread_count_key(user_id), count, timeout=timeout)


# ═══════════════════════════════════════════════════════════
# NOTIFICATIONS — with filter_suffix support
# ═══════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════
# NOTIFICATIONS — with filter_suffix support
# ═══════════════════════════════════════════════════════════

def get_cached_notifications(user_id, filter_suffix=None):
    """Get cached notifications — with optional filter suffix"""
    if filter_suffix:
        return cache.get(f'{_user_notifications_key(user_id)}_{filter_suffix}')
    return cache.get(_user_notifications_key(user_id))


def set_cached_notifications(user_id, data, filter_suffix=None, timeout=60):
    """Set cached notifications — with optional filter suffix"""
    if filter_suffix:
        cache.set(
            f'{_user_notifications_key(user_id)}_{filter_suffix}',
            data,
            timeout=timeout,
        )
    else:
        cache.set(_user_notifications_key(user_id), data, timeout=timeout)


def get_cached_unread_notifications(user_id):
    return cache.get(_unread_notifications_key(user_id))


def set_cached_unread_notifications(user_id, count, timeout=60):
    cache.set(_unread_notifications_key(user_id), count, timeout=timeout)


def invalidate_notifications_cache(user_id):
    """Notification create/read/delete ke baad — sab filter suffixes clear"""
    try:
        # ✅ Base keys
        cache.delete(_user_notifications_key(user_id))
        cache.delete(_unread_notifications_key(user_id))
        
        # ✅ Saare possible filter suffixes clear karo
        suffixes = [
            'all_all', 'all_unread',
            'result_published_all', 'result_published_unread',
            'prize_paid_all', 'prize_paid_unread',
            'points_earned_all', 'points_earned_unread',
            'tournament_completed_all', 'tournament_completed_unread',
            'payment_verified_all', 'payment_verified_unread',
            'payment_rejected_all', 'payment_rejected_unread',
            'account_blocked_all', 'account_blocked_unread',
            'payments_all', 'payments_unread',
        ]
        for s in suffixes:
            cache.delete(f'{_user_notifications_key(user_id)}_{s}')
        
        logger.info(f'🗑️  Notifications invalidated: user_{user_id}')
    except Exception as e:
        logger.exception(f'⚠️  Error: {e}')

# ═══════════════════════════════════════════════════════════
# TOURNAMENTS
# ═══════════════════════════════════════════════════════════

def get_cached_tournaments_list(filters='all'):
    return cache.get(_tournaments_list_key(filters))


def set_cached_tournaments_list(data, filters='all', timeout=300):
    cache.set(_tournaments_list_key(filters), data, timeout=timeout)


def get_cached_tournament_detail(tournament_id):
    return cache.get(_tournament_detail_key(tournament_id))


def set_cached_tournament_detail(tournament_id, data, timeout=300):
    cache.set(_tournament_detail_key(tournament_id), data, timeout=timeout)


# ═══════════════════════════════════════════════════════════
# MATCHES
# ═══════════════════════════════════════════════════════════

def get_cached_matches_list(filters='all'):
    return cache.get(_matches_list_key(filters))


def set_cached_matches_list(data, filters='all', timeout=300):
    cache.set(_matches_list_key(filters), data, timeout=timeout)


def get_cached_match_detail(match_id):
    return cache.get(_match_detail_key(match_id))


def set_cached_match_detail(match_id, data, timeout=300):
    cache.set(_match_detail_key(match_id), data, timeout=timeout)


# ═══════════════════════════════════════════════════════════
# REGISTRATIONS
# ═══════════════════════════════════════════════════════════

def get_cached_tournament_registrations(tournament_id):
    return cache.get(_tournament_registrations_key(tournament_id))


def set_cached_tournament_registrations(tournament_id, data, timeout=120):
    cache.set(_tournament_registrations_key(tournament_id), data, timeout=timeout)


# ═══════════════════════════════════════════════════════════
# USERS
# ═══════════════════════════════════════════════════════════

def get_cached_users_list(filters='all'):
    return cache.get(_users_list_key(filters))


def set_cached_users_list(data, filters='all', timeout=300):
    cache.set(_users_list_key(filters), data, timeout=timeout)


def get_cached_user_detail(user_id):
    return cache.get(_user_detail_key(user_id))


def set_cached_user_detail(user_id, data, timeout=300):
    cache.set(_user_detail_key(user_id), data, timeout=timeout)