from collections import deque
from dataclasses import dataclass
from itertools import chain
from entities.models import Food, SupplyStation
from ai.pathfinding import neighbors, distance
from systems.perks import record_collection

TIERS = {'micro': (1, 2), 'small': (5, 4), 'medium': (10, 8), 'large': (25, 16)}
DOWNGRADE = {'large': 'medium', 'medium': 'small', 'small': 'micro', 'micro': 'micro'}

@dataclass
class PendingDrop:
    origin: tuple
    units: float
    radius: int = 0
    cursor: int = 0


class FoodSystem:
    def __init__(self, world):
        self.world = world
        self.scent = {}
        self.footprints = {}
        self.pending = []
        self.pending_drops = []
        self.dropped_units = 0
        self.direct_consumed = 0
        self.generated = 0
        self.generated_units = 0
        self.initial_units = sum(f.units for f in world.food)
        self.harvested = 0
        self.delivered = 0
        self.eaten = 0
        self.discarded = 0
        self.trophy_created = 0
        self.rebuild_scent()

    def source(self, food_id):
        return next((f for f in self.sources() if f.id == food_id), None)

    def sources(self):
        return chain(self.world.food, self.world.stations)

    def rebuild_scent(self):
        self.scent.clear()
        terrain = self.world.terrain
        for food in self.sources():
            if food.units <= 0:
                continue
            topology = terrain.topology_version_near(food.position, food.max_scent)
            key = food.id, food.position, food.max_scent, topology
            if key not in self.footprints:
                # Geodesic diffusion through traversable cardinal cells; no scent through stone.
                distances = {food.position: 0}
                queue = deque([food.position])
                while queue:
                    p = queue.popleft()
                    if distances[p] == food.max_scent:
                        continue
                    for q in neighbors(terrain, p):
                        if q not in distances:
                            distances[q] = distances[p] + 1
                            queue.append(q)
                # Discard superseded cache entries for this source.
                self.footprints = {k: v for k, v in self.footprints.items() if k[0] != food.id}
                self.footprints[key] = distances
            radius = min(food.age, food.max_scent)
            for p, d in self.footprints[key].items():
                if d <= radius:
                    value = (food.max_scent + 1-d)/(food.max_scent+1)
                    self.scent[p] = max(self.scent.get(p, 0), value)

    def sample(self, position):
        return self.scent.get(position, 0.0)

    def harvest(self, food, turn, amount=1, ant=None):
        if food is None or food.units <= 0 or ant is not None and ant.kind == 'honeypot':
            return False
        amount = min(amount, food.units)
        if amount <= 0 or amount*2 != int(amount*2):
            return False
        if ant is not None and not isinstance(food, SupplyStation):
            record_collection(self.world.colonies[ant.faction], food)
        food.units -= amount
        self.harvested += amount
        if isinstance(food, SupplyStation):
            food.collected_units += amount
            if food.units == 0:
                food.age = 0
        elif food.units == 0:
            food.respawn_deadline = None if food.tier in ('trophy', 'drop') else turn + self.world.config.respawn_delay
        return amount

    def _drop_valid(self, position, occupied):
        x, y = position
        w = self.world
        return (0 <= x < w.config.size and 0 <= y < w.config.size and w.terrain.capacity[y,x]
                and position not in occupied and position not in w.structure_cells
                and position not in w.depot_claims and position not in w.construction_sites)

    def _drop_food(self, position, units):
        self.world.food.append(Food(self.world.allocate_id(), position, 'drop', units,
                                    self.world.config.honeypot_drop_scent))

    def drop(self, position, units):
        if units <= 0:
            return
        # This ledger is a transfer statistic, never a generation source.
        self.dropped_units += units
        occupied = {f.position for f in self.sources()}
        if self._drop_valid(position, occupied):
            self._drop_food(position, units)
        else:
            self.pending_drops.append(PendingDrop(position, units))
            self.place_drops()

    def place_drops(self):
        budget = self.world.config.drop_placement_budget
        occupied = {f.position for f in self.sources()}
        for job in list(self.pending_drops):
            if budget <= 0:
                break
            if job.radius > 2*self.world.config.size:
                if self.world.turn % 25:
                    continue
                job.radius, job.cursor = 0, 0
            placed = False
            while budget and job.radius <= 2*self.world.config.size:
                ox, oy = job.origin
                r = job.radius
                ring = sorted({(ox+dx, oy+dy) for dx in range(-r,r+1)
                               for dy in (-(r-abs(dx)),r-abs(dx))
                               if 0 <= ox+dx < self.world.config.size and 0 <= oy+dy < self.world.config.size})
                while job.cursor < len(ring) and budget:
                    p = ring[job.cursor];job.cursor += 1;budget -= 1
                    if self._drop_valid(p, occupied):
                        self._drop_food(p, job.units);occupied.add(p)
                        self.pending_drops.remove(job);placed = True;break
                if placed:
                    break
                if job.cursor >= len(ring):
                    job.radius += 1;job.cursor = 0

    def trophy(self, colony):
        world = self.world
        p = colony.queen.position
        nearby = [f for f in world.food if (p[0]-f.position[0])**2+(p[1]-f.position[1])**2 < world.config.food_spacing**2]
        if nearby:
            food = min(nearby, key=lambda f: (distance(p, f.position), f.id))
            food.units += world.config.trophy_units
            food.tier, food.max_scent = 'trophy', world.config.trophy_scent
            food.age, food.respawn_deadline = 0, None
        else:
            world.food.append(Food(world.allocate_id(), p, 'trophy', world.config.trophy_units, world.config.trophy_scent))
        self.trophy_created += world.config.trophy_units

    def _place(self, tier, central):
        world = self.world
        n = world.config.size
        radius = max(8, int(n*world.config.center_radius_fraction))
        # Random starting offset plus complete fallback scan: never silently overlap sources.
        candidates = world.food_candidates
        start = world.rng.randrange(len(candidates))
        for i in range(len(candidates)):
            p = candidates[(start+i) % len(candidates)]
            if (not world.terrain.capacity[p[1], p[0]] or p in world.structure_cells
                    or p in world.depot_claims):
                continue
            if central and (p[0]-(n-1)/2)**2+(p[1]-(n-1)/2)**2 > radius**2:
                continue
            if any((p[0]-f.position[0])**2+(p[1]-f.position[1])**2 < world.config.food_spacing**2 for f in world.food):
                continue
            units, scent = TIERS[tier]
            world.food.append(Food(world.allocate_id(), p, tier, units, scent))
            self.generated += 1
            self.generated_units += units
            return True
        return False

    def tick(self, turn):
        exhausted = {f.id for f in self.world.food if f.tier == 'drop' and f.units <= 0}
        if exhausted:
            self.world.food = [f for f in self.world.food if f.id not in exhausted]
            self.footprints = {k:v for k,v in self.footprints.items() if k[0] not in exhausted}
        if self.pending_drops:
            self.place_drops()
        for food in self.world.food:
            if food.units > 0:
                food.age = min(food.max_scent, food.age+1)
            elif food.respawn_deadline is not None and turn >= food.respawn_deadline:
                next_tier = self.world.config.micro_respawn_tier if food.tier == 'micro' else DOWNGRADE[food.tier]
                for colony in self.world.colonies:
                    if next_tier is not None and colony.active_perk == 'greed' and colony.greed_credits.get(food.tier, 0) > 0:
                        colony.greed_credits[food.tier] -= 1
                        next_tier = food.tier
                        break
                if next_tier is None:
                    food.respawn_deadline = None
                    continue
                food.tier = next_tier
                food.units, food.max_scent = TIERS[food.tier]
                self.generated_units += food.units
                food.age, food.respawn_deadline = 0, None
                food.generation += 1
        scheduled = []
        if turn % 50 == 0:
            scheduled += [('small', False)]*4
        if turn % 75 == 0:
            scheduled += [('medium', False)]*2
        if turn % 100 == 0:
            scheduled += [('large', True)]
        if scheduled or (self.pending and turn % 25 == 0):
            pending, self.pending = self.pending + scheduled, []
            for tier, central in pending:
                if not self._place(tier, central):
                    self.pending.append((tier, central))
        for station in self.world.stations:
            if station.units > 0:
                station.age = min(station.max_scent,station.age+1)

    def visible(self, position, sensing=2):
        return [f for f in self.sources() if f.units > 0 and distance(position, f.position) <= sensing]

    def accounting(self):
        """Signed inventories and cumulative sinks/sources; transfers cancel out.

        Manual test/benchmark injections require a closed-interval delta rather
        than comparison to initial world allocation.
        """
        w = self.world
        inventory = sum(j.units for j in self.pending_drops) + sum(a.stored_food for a in w.ants) + sum(f.units for f in self.sources()) + sum(a.cargo for a in w.ants) + sum(c.reserves for c in w.colonies)
        consumed = self.eaten+self.discarded+sum((c.spent_half+c.upkeep_spent_half+c.healing_spent_half+c.depot_spent_half)/2 for c in w.colonies)
        generated = self.generated_units+self.trophy_created+sum(s.generated_units for s in w.stations)
        initial = self.initial_units+5*len(w.stations)
        return dict(inventory=inventory,consumed=consumed,generated=generated,initial=initial,
                    residual=inventory+consumed-generated-initial)
