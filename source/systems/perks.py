"""Derived attributes always consult the live queen; no stale perk buffs survive death."""

def movement(ant, colony):
    if ant.kind == 'honeypot':
        return 1
    if ant.kind == 'soldier':
        return 4 if colony.active_perk == 'blitz' else 3
    return 3 if colony.active_perk == 'speed' else 2

def sensing(ant, colony):
    return 3 if ant.kind == 'soldier' or colony.active_perk == 'sensitivity' else 2

def load(ant, colony):
    if ant.kind == 'honeypot':
        return 0  # Dedicated storage is not ordinary carrying capacity.
    return 1.5 if colony.active_perk == 'heavy-lifting' else 1

def cost_half(kind, colony):
    if kind == 'honeypot':
        return 10  # Confirmed exact cost; no worker/soldier discount or free bonus.
    discount = (kind == 'worker' and colony.active_perk == 'exploration') or (kind == 'soldier' and colony.active_perk == 'warfare')
    return 3 if discount else 4

def queen_sensing(colony, config):
    return 15 if colony.active_perk == 'sensitivity' else config.queen_alarm_radius

def record_collection(colony, food):
    if colony.active_perk != 'greed' or food.tier in ('trophy', 'drop'):
        return
    seen = colony.greed_seen.setdefault(food.tier, set())
    seen.add(food.id)
    if len(seen) >= 5:
        colony.greed_credits[food.tier] = colony.greed_credits.get(food.tier, 0) + 1
        seen.clear()
