"""Read-only food diagnostics; no simulation updates or random calls."""
from systems.economy import food_upkeep
NAMES = ('Red','Yellow','Blue','Green')

def economy_lines(engine):
    populations = engine.economy.populations()
    next_upkeep = 100-engine.turn%100
    lines = []
    for c in engine.world.colonies:
        starving = c.alive and c.reserves < 0
        next_damage = str(2-c.starvation_turns%2)+' turns' if starving else '--'
        lines += [f'{NAMES[c.faction].upper()} FOOD ECONOMY',
                  f'Upkeep population {populations[c.faction]} | reserve {c.reserves:g}',
                  f'Honeypots {sum(a.kind == "honeypot" and a.faction == c.faction for a in engine.world.ants)} | stored {sum(a.stored_food for a in engine.world.ants if a.faction == c.faction):g}',
                  f'Upkeep {food_upkeep(populations[c.faction])}/100 | next {next_upkeep} turns',
                  f'Debt {max(0,-c.reserves):g} | Queen {c.queen.hp:g}/{c.queen.max_hp:g}',
                  f'Starvation {"ACTIVE" if starving else "off"} | next {next_damage}',
                  f'Last healing +{c.last_healing:g} HP | food {c.last_healing_food:g}',
                  f'{c.strategic_state} | target reserve {c.reserve_target}',
                  f'Depot receipts {sum(d.deposited for d in engine.world.depots if d.faction == c.faction):g} (included in shared food)',
                  f'Upkeep sources {c.upkeep_source_half/2:g} | H supply {c.upkeep_honeypot_half/2:g}',
                  f'Spent: upkeep {c.upkeep_spent_half/2:g} | healing {c.healing_spent_half/2:g}']
    stations = engine.world.stations
    countdown = min((s.next_refill-engine.turn for s in stations),default=0)
    lines += [f'PUBLIC SUPPLY STATIONS: {len(stations)}',
              f'At stations {sum(s.units for s in stations):g} | carried {sum(a.cargo for a in engine.world.ants):g}',
              f'Delivered {engine.food.delivered:g} | refill in {countdown} turns',
              f'Latest refill +{engine.supply.last_refill_units:g} (turn {engine.supply.last_refill_turn})',
              f'Initial {engine.supply.initial_units:g} | refill total {engine.supply.generated_units:g}',
              'White + square: public supply station']
    return lines
