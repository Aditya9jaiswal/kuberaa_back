# apps/results/utils/prize_calculator.py
"""
Prize Calculation Logic
========================
Formula: Per Kill = Entry Fee × 0.75
- ₹10  match → ₹7.5  per kill
- ₹20  match → ₹15   per kill
- ₹50  match → ₹37.5 per kill
"""

from decimal import Decimal, ROUND_HALF_UP


def calculate_per_kill_prize(entry_fee):
    """Entry fee × 0.75 → per kill prize"""
    try:
        entry_fee = Decimal(str(entry_fee or 0))
    except Exception:
        entry_fee = Decimal('0')

    per_kill = entry_fee * Decimal('0.75')
    return per_kill.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_prize_amount(entry_fee, kills):
    """Total prize = kills × per_kill_prize"""
    kills = int(kills or 0)
    if kills <= 0:
        return Decimal('0.00')

    per_kill = calculate_per_kill_prize(entry_fee)
    total = per_kill * Decimal(str(kills))
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_score(kills, placement):
    """Score = (kills × 10) + placement bonus"""
    kills = int(kills or 0)
    placement = int(placement or 0)

    kill_points = kills * 10

    if placement == 1:
        placement_points = 20
    elif placement == 2:
        placement_points = 15
    elif placement == 3:
        placement_points = 10
    elif placement > 0:
        placement_points = 5
    else:
        placement_points = 0

    return kill_points + placement_points