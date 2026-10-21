from entities.models import Ant
from ai.pathfinding import neighbors
from systems.perks import cost_half, movement
from systems.strategy import update_reserves, reserve_target

class Reproduction:
    def __init__(self, world):
        self.world = world

    def spawn_space(self, colony):
        t = self.world.terrain
        cells = {q for p in colony.queen.footprint for q in neighbors(t, p) if t.available(*q)}
        return min(cells, key=lambda p: (int(t.occupancy[p[1], p[0]]), p)) if cells else None

    def tick(self, turn):
        if not self.world.config.reproduction_enabled:
            return
        update_reserves(self.world)
        counts = [sum(a.hp > 0 and a.kind != 'honeypot' and a.faction == f for a in self.world.ants) for f in range(4)]
        for colony in self.world.colonies:
            if not colony.alive or colony.last_queen_action_turn == turn:
                continue
            policy_floor = (2*colony.reserve_target if self.world.config.strategic_reserves_enabled
                            and colony.strategic_state != 'Total War' else 0)
            saving = self.world.depot_system.savings_floor(colony.faction)
            policy_floor += 2*saving
            automatic = colony.active_perk == 'production' and colony.produced_workers >= 10
            if automatic:
                colony.upgraded = True
            colony.saving_upgrade = False
            if not colony.upgraded and colony.reserves_half >= self.world.config.upgrade_cost_half+policy_floor:
                cost = self.world.config.upgrade_cost_half
                colony.reserves = (colony.reserves_half-cost)/2
                colony.spent_half += cost
                colony.upgrade_spent_half += cost
                colony.upgraded = True
                colony.last_queen_action_turn = turn
                continue  # Paid upgrade uses this queen's turn; no birth as well.
            if not colony.upgraded and colony.active_perk != 'production':
                workers = sum(a.faction == colony.faction and a.kind == 'worker' and a.hp > 0 for a in self.world.ants)
                if workers >= self.world.config.upgrade_save_worker_threshold or (workers >= 2 and colony.threat in ('contact', 'near-base', 'critical')):
                    colony.saving_upgrade = True
                    continue
            space = self.spawn_space(colony)
            if space is None:
                continue
            bonus = bool(colony.active_perk == 'production' and colony.bonus_queue)
            percentage = self.world.config.soldier_percentages[('safe', 'alert', 'contact', 'near-base', 'critical').index(colony.threat)]
            if colony.strategic_state == 'Total War':
                percentage = 100
            elif colony.strategic_state == 'Alert':
                percentage = max(50, percentage)
            credit = colony.soldier_credit + (percentage if colony.upgraded else 0)
            kind = colony.bonus_queue[0] if bonus else ('soldier' if colony.upgraded and credit >= 100 else 'worker')
            if colony.strategic_state == 'Total War' and colony.upgraded and not bonus:
                kind = 'soldier'
            if (not bonus and colony.upgraded and self.world.config.honeypots_enabled and colony.strategic_state != 'Total War'
                    and colony.threat in ('safe','alert')):
                workers = sum(a.hp > 0 and a.kind == 'worker' and a.faction == colony.faction for a in self.world.ants)
                honeypots = sum(a.hp > 0 and a.kind == 'honeypot' and a.faction == colony.faction for a in self.world.ants)
                desired = (workers+self.world.config.honeypot_workers_per_unit-1)//self.world.config.honeypot_workers_per_unit
                if (workers >= self.world.config.honeypot_min_workers and honeypots < desired
                        and colony.reserves_half >= 10+policy_floor):
                    kind = 'honeypot'
            if kind == 'soldier' and not colony.upgraded:
                continue
            cost = 0 if bonus and kind != 'honeypot' else cost_half(kind, colony)
            floor = (2*reserve_target(self.world.config, counts[colony.faction]+(kind != 'honeypot')) if self.world.config.strategic_reserves_enabled
                     and colony.strategic_state != 'Total War' else 0)
            floor += 2*saving
            if colony.reserves_half < 0 or colony.reserves_half < cost or (cost and colony.reserves_half-cost < floor):
                continue
            colony.reserves = (colony.reserves_half-cost)/2
            colony.spent_half += cost
            if bonus:
                colony.bonus_queue.pop(0)
                colony.bonus_births += 1
            elif kind != 'honeypot':
                colony.soldier_credit = credit-100 if kind == 'soldier' else credit
            ant = Ant(self.world.allocate_id(), colony.faction, space, kind=kind)
            ant.planned_budget = movement(ant, colony)
            ant.path = [space]*(ant.planned_budget+1)
            self.world.ants.append(ant)
            self.world.terrain.occupancy[space[1], space[0]] += 1
            if kind == 'worker':
                colony.produced_workers += 1
            elif kind == 'soldier':
                colony.produced_soldiers += 1
            else:
                colony.produced_honeypots += 1
            if colony.active_perk == 'production' and kind != 'honeypot':
                if colony.upgraded:
                    colony.post_upgrade_counts[kind] += 1
                    if colony.post_upgrade_counts[kind] % 10 == 0:
                        colony.bonus_queue.append(kind)
                if colony.produced_workers >= 10:
                    colony.upgraded = True
            colony.last_birth_turn = colony.last_queen_action_turn = turn

        update_reserves(self.world)
