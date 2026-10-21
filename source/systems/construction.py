"""Local, bounded construction jobs and physical material transactions.

Food, healing and combat take precedence. Recruitment retains at least one
worker and uses a proportional workforce budget rather than a population cap.
"""
from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from ai.pathfinding import distance, neighbors
from simulation.terrain import SOIL, PASSAGE, REINFORCED
from simulation.spatial import SpatialIndex
from systems.perks import load
from systems.stones import Stones, CARDINAL, speed_ratio

@dataclass
class Task:
    id: int
    faction: int
    kind: str
    target: tuple
    stones: tuple = ()
    direction: tuple = (0, 0)
    crew: list = field(default_factory=list)
    progress: Fraction = field(default_factory=Fraction)
    soil: int = 0
    created: int = 0
    paid_half: int = 0
    last_work_turn: int = -1
    active_builders: int = 0
    blocked_reason: str = "awaiting builders"
    contributions: dict = field(default_factory=dict)

class Construction:
    def __init__(self, world):
        self.world = world
        world.construction_system = self
        world.construction_sites = set()
        self.stones = Stones(world)
        self.tasks = {}
        self.next_id = 0
        self.completed = Counter()
        self.cooldown = {}
        self.assignments = {}

    def soil_total(self):
        t = self.world.terrain
        return (int(t.layers.sum()) + sum(t.loose_soil.values())
                + sum(a.soil_cargo for a in self.world.ants)
                + sum(s.bound_soil for s in self.stones.groups.values())
                + sum(job.soil for job in self.tasks.values()))

    def eligible(self, ant):
        colony = self.world.colonies[ant.faction]
        return (ant.hp > 0 and ant.kind != 'honeypot' and not ant.cargo and ant.combat_target is None
                and ant.state not in ('fight', 'defend', 'forage-to-heal', 'return-report', 'investigate', 'delivery-plan', 'offensive')
                and (colony.alive or ant.hp == ant.max_hp))

    def cells_near(self, p, radius):
        x, y = p
        n = self.world.config.size
        for cy in range(max(0, y-radius), min(n, y+radius+1)):
            for cx in range(max(0, x-radius), min(n, x+radius+1)):
                if abs(cx-x)+abs(cy-y) <= radius:
                    yield cx, cy

    def local_stones(self, p, radius):
        t = self.world.terrain
        return sorted({int(t.stone_ids[y, x]) for x, y in self.cells_near(p, radius)
                       if t.stone_ids[y, x] >= 0})

    def work_cells(self, job):
        t = self.world.terrain
        if job.kind == 'depot':
            footprint = set(self.world.depot_system.cells(job.target))
            return sorted({q for p in footprint for q in neighbors(t, p) if q not in footprint})
        if job.kind == 'stone':
            stone = self.stones.groups.get(job.stones[0])
            if stone is None:
                return []
            forbidden = set(self.stones.destination(stone, job.direction))
            cells = {q for p in stone.cells for q in self.cells_near(p, self.world.config.stone_work_radius)
                     if q not in forbidden and t.capacity[q[1], q[0]]}
        else:
            cells = {p for p in self.cells_near(job.target, 1) if t.capacity[p[1], p[0]]}
        return sorted(cells)

    def create(self, faction, kind, target, stones=(), direction=(0, 0)):
        if any(j.faction == faction for j in self.tasks.values()):
            return None
        if target in self.world.construction_sites or any(set(stones).intersection(j.stones) for j in self.tasks.values()):
            return None  # one exclusive worksite/stone claim, including foreign crews
        if kind == 'stone':
            stone = self.stones.groups.get(stones[0]) if len(stones) == 1 else None
            if stone is None or target not in stone.cells or not self.stones.can_move(stone, direction):
                return None
        elif kind == 'depot':
            if not self.world.config.depots_enabled or not self.world.colonies[faction].alive or not self.world.depot_system.valid(target):
                return None
        elif kind == 'compose':
            if (not self.stones.can_compose(stones) or not self.stones.in_bounds(target)
                    or not self.world.terrain.capacity[target[1], target[0]]
                    or any(f.position == target for f in self.world.food)):
                return None
            # A deposit site must physically touch both component footprints.
            a, b = (self.stones.groups[i] for i in stones)
            radius = self.world.config.composition_access_radius
            if min(distance(target, p) for p in a.cells) > radius or min(distance(target, p) for p in b.cells) > radius:
                return None
        else:
            raise ValueError('Unknown coordinated construction task')
        job = Task(self.next_id, faction, kind, target, tuple(stones), direction, created=self.world.turn)
        if not self.stones.in_bounds(target) or not self.work_cells(job):
            return None
        if kind == "depot" and sum(int(self.world.terrain.capacity[y,x]) for x,y in self.work_cells(job)) < 2:
            return None
        if kind == "depot" and not self.world.depot_system.commit(job):
            return None
        self.next_id += 1
        if kind == 'depot':
            self.world.depot_claims.update(self.world.depot_system.cells(target))
        self.tasks[job.id] = job
        self.world.construction_sites.add(job.target)
        return job

    def blocked_route(self, ant, position, goal):
        if (not self.world.config.construction_enabled or not self.eligible(ant)
                or self.cooldown.get(ant.faction, 0) > self.world.turn
                or ant.construction_task is not None
                or any(j.faction == ant.faction for j in self.tasks.values())):
            return
        for sid in self.local_stones(position, 2):
            stone = self.stones.groups[sid]
            if min(distance(p, goal) for p in stone.cells) >= distance(position, goal):
                continue
            for direction in CARDINAL:
                dest = self.stones.destination(stone, direction)
                if goal not in dest and position not in dest:
                    job = self.create(ant.faction, 'stone', stone.cells[0], (sid,), direction)
                    if job:
                        # Recruit before nearby idle helpers disperse during this
                        # planning interval. Already spent movement stays spent.
                        self.recruit(job)
                        return

    def finish(self, job, completed=False):
        if job.soil:
            self.world.terrain.deposit(job.target, job.soil)
            job.soil = 0
        if job.kind == 'depot':
            self.world.depot_claims.difference_update(self.world.depot_system.cells(job.target))
        for ant in self.world.ants:
            if ant.construction_task == job.id:
                ant.construction_task = None
        self.tasks.pop(job.id, None)
        self.world.construction_sites.discard(job.target)
        self.cooldown[job.faction] = self.world.turn + self.world.config.construction_cooldown
        if completed:
            self.completed[job.kind] += 1

    def begin_plan(self):
        self.assignments.clear()
        for a in self.world.ants:
            job = self.tasks.get(a.construction_task)
            if job is None or job.kind != "depot":
                a.construction_task = None
        if not self.world.config.construction_enabled:
            return
        self.index = SpatialIndex(self.world.ants)
        self.population = Counter(a.faction for a in self.world.ants if a.kind != 'honeypot')
        for job in list(self.tasks.values()):
            if (job.kind != "depot" and self.world.turn-job.created >= self.world.config.construction_timeout
                    or any(i not in self.stones.groups for i in job.stones)
                    or job.kind == 'depot' and not self.world.colonies[job.faction].alive):
                self.finish(job)
        # Only useful local evidence initiates a job: blocked traffic or soil that
        # can bind an existing near-base stone seam. No per-ant map searches.
        for ant in self.world.ants:
            if not self.eligible(ant) or self.cooldown.get(ant.faction, 0) > self.world.turn:
                continue
            if any(j.faction == ant.faction for j in self.tasks.values()):
                continue
            self.world.depot_system.propose(ant, self)
            if any(j.faction == ant.faction for j in self.tasks.values()):
                continue
            ids = self.local_stones(ant.position, 2) if ant.blocked_turns >= 2 or ant.soil_cargo else []
            if ant.blocked_turns >= 2 and ant.target is not None:
                for sid in ids:
                    stone = self.stones.groups[sid]
                    # The stone lies toward a real food/base/patrol target.
                    if min(distance(p, ant.target) for p in stone.cells) >= distance(ant.position, ant.target):
                        continue
                    for direction in CARDINAL:
                        dest = self.stones.destination(stone, direction)
                        if ant.target in dest or ant.position in dest:
                            continue
                        if self.create(ant.faction, 'stone', stone.cells[0], (sid,), direction):
                            break
                    if any(j.faction == ant.faction for j in self.tasks.values()):
                        break
            if ant.soil_cargo and self.near_home(ant.position, ant.faction):
                material = sum(self.world.terrain.loose_soil.get(p, 0)
                               for p in self.cells_near(ant.position, self.world.config.construction_radius)
                               if self.world.terrain.capacity[p[1], p[0]])
                material += sum(a.soil_cargo for a in self.index.near(ant.position, self.world.config.construction_radius)
                                if a.faction == ant.faction and self.eligible(a))
                if material < self.world.config.composition_soil:
                    continue
                for i, sid in enumerate(ids):
                    for other in ids[i+1:]:
                        if self.create(ant.faction, 'compose', ant.position, (sid, other)):
                            break
                    if any(j.faction == ant.faction for j in self.tasks.values()):
                        break
        # Fresh jobs and old jobs use the same real recruitment path.
        for job in list(self.tasks.values()):
            self.recruit(job)

    def near_home(self, p, faction):
        return min(distance(p, q) for q in self.world.colonies[faction].queen.footprint) <= self.world.config.nest_clearance+2

    def fill_targets(self, position, faction):
        t = self.world.terrain
        return [p for p in self.cells_near(position, 1)
                if t.cells[p[1], p[0]] in (SOIL, REINFORCED)
                and t.layers[p[1], p[0]] < self.world.config.max_soil_layers
                and t.traffic[p[1], p[0]] < self.world.config.busy_path_visits
                and t.occupancy[p[1], p[0]] <= 1
                and all(f.position != p for f in self.world.food)
                and min(distance(p, q) for q in self.world.colonies[faction].queen.footprint) >= 2]

    def recruit(self, job):
        if job.kind == "depot":
            return self.recruit_depot(job)
        world = self.world
        maximum = min(self.population[job.faction]-1,
                      max(1, int(self.population[job.faction]*world.config.construction_fraction)))
        candidates = sorted((a for a in self.index.near(job.target, world.config.construction_radius)
                             if a.faction == job.faction and self.eligible(a)
                             and not (a.order_state == 'Total War' and a.id in world.orders.logistics)
                             and (job.kind != 'stone' or not a.soil_cargo)
                             and (job.kind == 'depot' or a.kind == 'soldier' or not a.known_food)), key=lambda a: (a.id not in job.crew, distance(a.position, job.target), a.id))
        # Always leave a worker outside the crew when workers exist.
        workers = [a.id for a in world.ants if a.faction == job.faction and a.kind == 'worker']
        if workers and set(workers).issubset({a.id for a in candidates}):
            candidates = [a for a in candidates if a.id != workers[-1]]
        crew = candidates[:max(0, maximum)]
        if job.kind == 'stone':
            stone = self.stones.groups.get(job.stones[0])
            capacity = sum(load(a, world.colonies[a.faction]) for a in crew)
            if stone is None or not speed_ratio(capacity, stone.weight, world.config):
                job.crew = []
                return  # insufficient nearby support never immobilizes idle ants
        cells = self.work_cells(job)
        crew_ids = {a.id for a in crew}
        slots = Counter(a.position for a in world.ants if a.id not in crew_ids and a.hp > 0)
        job.crew = []
        for ant in crew:
            if job.kind == 'compose' and not ant.soil_cargo:
                stores = [p for p in self.cells_near(job.target, world.config.construction_radius)
                          if world.terrain.loose_soil.get(p) and world.terrain.capacity[p[1], p[0]]]
                if not stores:
                    continue
                target = min(stores, key=lambda p: (distance(ant.position, p), p))
                state = 'collect-soil'
            else:
                available = [p for p in cells if slots[p] < world.terrain.capacity[p[1], p[0]]]
                if not available:
                    break
                target = min(available, key=lambda p: (distance(ant.position, p), p))
                slots[target] += 1
                state = 'build-depot' if job.kind == 'depot' else ('move-stone' if job.kind == 'stone' else 'compose-stone')
            ant.state, ant.target, ant.construction_task = state, target, job.id
            job.crew.append(ant.id)
            self.assignments[ant.id] = job.id

    def resume_depot(self, ant):
        job = self.tasks.get(ant.construction_task)
        if (job is None or job.kind != 'depot' or ant.kind != 'worker'
                or not self.world.colonies[ant.faction].alive or ant.cargo or ant.soil_cargo):
            return False
        # Called only after immediate combat/defense and queenless survival branches.
        ant.state = 'build-depot'
        if ant.target not in self.work_cells(job):
            ant.target = ant.position  # recruitment selects an approach later in this plan
        return True

    def recruit_depot(self, job):
        w = self.world
        workers = [a for a in w.ants if a.hp > 0 and a.faction == job.faction and a.kind == 'worker']
        maximum = max(0, min(w.config.depot_builder_limit, max(2,len(workers)-1), max(2, int(len(workers)*w.config.construction_fraction))))
        old = set(job.crew)
        members = [a for a in workers if a.id in old]
        candidates = sorted((a for a in workers if a.id not in old and a.combat_target is None
                             and a.state not in ('fight', 'defend', 'forage-to-heal', 'offensive')
                             and not (a.order_state == 'Total War' and a.id in w.orders.logistics)),
                            key=lambda a: (distance(a.position, job.target), a.id))
        crew = sorted(members, key=lambda a: a.id)[:maximum]
        crew += candidates[:max(0, maximum-len(crew))]
        cells = self.work_cells(job)
        ids = {a.id for a in crew}
        slots = Counter(a.position for a in w.ants if a.hp > 0 and a.id not in ids)
        job.crew = []
        for ant in crew:
            ant.construction_task = job.id
            job.crew.append(ant.id)
            self.assignments[ant.id] = job.id
            if not self.eligible(ant) or ant.soil_cargo:
                continue  # preserve assignment during immediate survival/combat interruption
            available = [p for p in cells if slots[p] < w.terrain.capacity[p[1], p[0]]]
            # A common shared field proves accessibility; only local approach choices differ.
            available.sort(key=lambda p: (p != ant.position, distance(ant.position, p), p))
            cost = w.navigation.region_cost(('build', job.faction, job.target), cells, ant.position)
            target = available[0] if available and cost not in (None, float('inf')) else None
            if target is None:
                ant.state, ant.target = 'build-depot', ant.position
                continue
            slots[target] += 1
            ant.state, ant.target = 'build-depot', target

    def prepare_idle(self, ant):
        """Solo material handling after higher-priority survival/food decisions."""
        if not self.world.config.construction_enabled or not self.eligible(ant):
            return False
        t = self.world.terrain
        behavior=self.world.behavior
        if (ant.kind=='worker' and not ant.soil_cargo and self.world.colonies[ant.faction].alive
                and behavior.due(ant) and ant.faction not in behavior.excavation_claims):
            opportunities=[f for f in self.world.information.latest(ant,('excavation',))
                           if distance(ant.position,f.position)<=1
                           and t.cells[f.position[1],f.position[0]]==SOIL
                           and t.traffic[f.position[1],f.position[0]]>=self.world.config.busy_path_visits]
            if opportunities:
                fact=max(opportunities,key=lambda f:(f.payload[0],f.observed,f.position))
                ant.state,ant.target,ant.dig_target='dig',ant.position,fact.position
                behavior.excavation_claims.add(ant.faction)
                return True
        if ant.soil_cargo:
            if self.near_home(ant.position, ant.faction):
                # Reinforce quiet outer approaches, never narrow a busy passage.
                candidates = self.fill_targets(ant.position, ant.faction)
                if candidates:
                    ant.state, ant.target = 'fill', min(candidates)
                    return True
            bases = [p for q in self.world.colonies[ant.faction].queen.footprint for p in neighbors(t, q)]
            ant.state = 'store-soil' if ant.position in bases else 'return-soil'
            ant.target = min(bases, key=lambda p: (distance(ant.position, p), p)) if bases else ant.position
            return True
        # A local stockpile is useful only near home; food gatherers are never
        # diverted here because their prepare branch already returned.
        stores = [p for p in self.cells_near(ant.position, 1)
                  if t.loose_soil.get(p) and t.capacity[p[1], p[0]] and self.near_home(p, ant.faction)
                  and self.fill_targets(p, ant.faction)]
        if stores:
            ant.state, ant.target = 'collect-soil', min(stores, key=lambda p: (distance(ant.position, p), p))
            return True
        return False

    def mark(self, ant, action, turn):
        ant.action_used, ant.last_action, ant.last_action_turn = True, action, turn

    def dig(self, ant, target, turn):
        if ant.hp <= 0 or ant.kind == 'honeypot' or ant.action_used or distance(ant.position, target) > 1:
            return False
        t = self.world.terrain
        if not t.dig(*target):
            return False
        if load(ant, self.world.colonies[ant.faction])-ant.cargo-ant.soil_cargo >= 1:
            t.withdraw(target)
            ant.soil_cargo += 1
        self.mark(ant, 'dig', turn)
        return True

    def action(self, ant, turn):
        if ant.hp <= 0 or ant.kind == 'honeypot' or ant.action_used:
            return False
        t = self.world.terrain
        if ant.state == 'collect-soil' and ant.target is not None and distance(ant.position, ant.target) <= 1:
            if load(ant, self.world.colonies[ant.faction])-ant.cargo-ant.soil_cargo >= 1 and t.withdraw(ant.target):
                ant.soil_cargo += 1
                self.mark(ant, 'collect-soil', turn)
                return True
        if ant.soil_cargo and ant.state == 'fill' and distance(ant.position, ant.target) <= 1:
            if all(f.position != ant.target for f in self.world.food) and t.fill(ant.target, self.world.config.max_soil_layers, ant):
                self.mark(ant, 'fill', turn)
                self.completed['fill'] += 1
                return True
        if ant.soil_cargo and ant.state in ('store-soil', 'return-soil') and ant.position == ant.target:
            t.deposit(ant.position, ant.soil_cargo)
            ant.soil_cargo = 0
            self.mark(ant, 'store-soil', turn)
            return True
        return False

    def resolve(self, turn):
        ants = {a.id: a for a in self.world.ants if a.hp > 0}
        for job in list(self.tasks.values()):
            crew = [ants[i] for i in job.crew if i in ants and not ants[i].action_used
                    and ants[i].faction == job.faction
                    and ants[i].construction_task == job.id and self.eligible(ants[i])]
            if job.kind == 'depot':
                if not self.world.colonies[job.faction].alive:
                    self.finish(job)
                    continue
                if job.last_work_turn == turn:
                    continue
                job.last_work_turn = turn
                cells = set(self.work_cells(job))
                crew = [ants[i] for i in sorted(set(job.crew)) if i in ants
                        and ants[i].kind == 'worker' and ants[i].faction == job.faction
                        and ants[i].construction_task == job.id and not ants[i].action_used
                        and self.eligible(ants[i]) and ants[i].position in cells]
                job.active_builders = len(crew)
                if len(crew) >= 2 and job.progress < 20:
                    job.progress += len(crew)
                    for ant in crew:
                        self.mark(ant, 'build-depot', turn)
                        job.contributions[ant.id] = job.contributions.get(ant.id, 0)+1
                    job.blocked_reason = 'working'
                elif job.progress < 20:
                    job.blocked_reason = 'fewer than two active workers'
                if job.progress >= 20 and self.world.depot_system.build(job, turn):
                    self.finish(job, True)
                continue
            if job.kind == 'stone':
                stone = self.stones.groups.get(job.stones[0])
                if stone is None:
                    self.finish(job)
                    continue
                cells = set(self.work_cells(job))
                crew = [a for a in crew if a.position in cells]
                capacity = sum(max(0, load(a, self.world.colonies[a.faction])-a.cargo-a.soil_cargo) for a in crew)
                rate = speed_ratio(capacity, stone.weight, self.world.config)
                if not rate or not self.stones.can_move(stone, job.direction):
                    continue
                job.progress += rate*Fraction(str(self.world.config.stone_base_speed))
                for ant in crew:
                    self.mark(ant, 'move-stone', turn)
                if job.progress >= 1 and self.stones.move(stone, job.direction):
                    # Jobs relocate one cardinal cell. Excess work cannot teleport
                    # beyond the validated destination or carry into another job.
                    self.finish(job, True)
            else:
                if not self.stones.can_compose(job.stones):
                    self.finish(job)
                    continue
                for ant in crew:
                    if not ant.soil_cargo or distance(ant.position, job.target) > 1:
                        continue
                    ant.soil_cargo -= 1
                    job.soil += 1
                    self.mark(ant, 'compose-stone', turn)
                    if job.soil == self.world.config.composition_soil:
                        self.stones.compose(job)
                        self.finish(job, True)
                        break
