"""Globally linked deposit endpoints and bounded, observation-driven project planning.

No depot holds spendable stock. Queenless endpoints disconnect permanently.
"""
from collections import Counter
from entities.models import Depot
from ai.pathfinding import distance, neighbors


class Depots:
    def __init__(self, world):
        self.world = world
        world.depots = []
        world.structure_cells = set()
        world.depot_claims = set()
        self.by_id, self.at_cell = {}, {}
        self.last_proposal, self.known, self.savings = {}, {}, {}
        self.events = []
        self.failures = Counter()
        self.next_id = self.completed = 0
        # Empty compatibility diagnostics; no hauling roles or inventory claims exist.
        self.logistics_workers, self.hauler_factions = set(), set()
        self.withdraw_claims, self.deposit_claims = {}, {}

    def event(self, kind, **data):
        self.events.append(dict(turn=self.world.turn, kind=kind, **data))
        # Bound model diagnostics; external gameplay recorder drains/copies each turn.
        if len(self.events) > 512:
            del self.events[:256]

    def cells(self, position):
        x, y = position
        width, height = self.world.config.depot_footprint
        return tuple((x+dx, y+dy) for dy in range(height) for dx in range(width))

    def get(self, ident, faction):
        depot = self.by_id.get(ident)
        return depot if depot is not None and depot.faction == faction else None

    def connected(self, depot):
        return self.world.colonies[depot.faction].alive

    def valid(self, position, own_claim=False):
        w = self.world
        foods = {f.position for f in (*w.food, *w.stations)}
        queens = {p for c in w.colonies for p in c.queen.footprint if c.alive}
        return all(0 <= x < w.config.size and 0 <= y < w.config.size
                   and w.terrain.capacity[y, x] and not w.terrain.occupancy[y, x]
                   and (x, y) not in foods | queens | w.structure_cells
                   and (own_claim or (x, y) not in w.depot_claims)
                   and ((own_claim and (x, y) == position) or (x, y) not in w.construction_sites)
                   for x, y in self.cells(position))

    def commit(self, job):
        c = self.world.colonies[job.faction]
        floor = c.reserve_target if self.world.config.strategic_reserves_enabled and c.strategic_state != 'Total War' else 0
        if job.paid_half or not c.alive or c.reserves < 15+floor:
            self.failures['unaffordable'] += 1
            return False
        c.reserves -= 15
        c.depot_spent_half += 30
        job.paid_half = 30
        self.savings.pop(c.faction, None)
        self.event('accepted', faction=c.faction, project=job.id, position=job.target)
        return True

    def build(self, job, turn):
        if job.paid_half != 30 or job.progress < 20 or not self.world.colonies[job.faction].alive:
            return False
        if not self.valid(job.target, own_claim=True):
            job.blocked_reason = 'footprint occupied or invalid'
            self.failures['completion blocked'] += 1
            return False
        depot = Depot(self.next_id, job.faction, job.target, self.world.config.depot_footprint)
        self.next_id += 1
        self.world.depots.append(depot)
        self.by_id[depot.id] = depot
        self.at_cell.update((p, depot.id) for p in depot.footprint)
        self.world.structure_cells.update(depot.footprint)
        self.completed += 1
        self.event('completed', faction=job.faction, project=job.id, depot=depot.id,
                   position=job.target, work=int(job.progress), builders=sorted(job.contributions), contributions=dict(job.contributions))
        return True

    def begin_plan(self):
        for f, (position, deadline) in list(self.savings.items()):
            c = self.world.colonies[f]
            if not c.alive or c.strategic_state == 'Total War' or self.world.turn >= deadline:
                self.savings.pop(f, None)

    def savings_floor(self, faction):
        c = self.world.colonies[faction]
        return 15 if c.alive and c.strategic_state == 'Peace' and faction in self.savings else 0

    def observe(self, ant):
        # Food evidence stays with its observer or physical gossip recipient.
        # The legacy registry remains diagnostic only and is never a faction telepathy source.
        return

    def prepare_healing(self, ant):
        return False  # Disconnected endpoints contain no local food to eat.

    def propose(self, ant, construction):
        w = self.world
        c = w.colonies[ant.faction]
        if not w.config.depots_enabled or ant.kind != 'worker' or not c.alive:
            return
        if w.turn < self.last_proposal.get(c.faction, -1):
            return
        self.last_proposal[c.faction] = w.turn+w.config.depot_proposal_interval
        workers = [a for a in w.ants if a.faction == c.faction and a.hp > 0 and a.kind == 'worker']
        if len(workers) < 3 or c.strategic_state == 'Total War' or c.threat in ('near-base', 'critical'):
            self.failures['workforce or defense'] += 1
            return
        known = ant.food_observations
        foods = sorted((v for v in known.values() if v[1] >= 5 or v[4]),
                       key=lambda v: (-v[1], v[0]))[:4]
        if not foods:
            self.failures['no valuable observed food'] += 1
            return
        available = [a for a in workers if a.combat_target is None
                     and a.state not in ("fight", "defend", "forage-to-heal", "offensive")]
        if len(available) < 2:
            self.failures["fewer than two available workers"] += 1
            return
        nav = w.navigation
        pending = False
        for source, stock, tier, observed, regenerates in foods:
            if sum(distance(source,v[0]) <= w.config.depot_food_radius for v in known.values()) < w.config.depot_min_sources:
                continue
            home = nav.region_cost(('home', c.faction), nav.home(c.faction), source)
            if home is None:
                pending = True
                continue
            if home == float('inf') or home < w.config.depot_home_distance:
                continue
            existing = home
            for d in w.depots:
                if d.faction == c.faction:
                    cost = nav.region_cost(('depot', d.id), d.footprint, source)
                    if cost is None:
                        pending = True
                        break
                    existing = min(existing, cost)
            if pending:
                continue
            candidates = sorted(construction.cells_near(source, 3),
                                key=lambda p: (distance(source, p), p))
            candidates = [p for p in candidates if self.valid(p)
                          and all(distance(p, d.position) >= w.config.depot_min_spacing
                                  for d in w.depots if d.faction == c.faction)][:w.config.depot_candidate_limit]
            for p in candidates:
                if ((ant.foreign_target is not None and distance(ant.foreign_target,p)<=w.config.construction_radius)
                        or any(distance(f.position,p)<=w.config.construction_radius
                               for f in w.information.latest(ant,('enemy','danger')))):
                    self.failures['observed danger'] += 1
                    continue
                cells = self.cells(p)
                cost = nav.region_cost(('proposed-depot', c.faction, source, p), cells, source)
                if cost is None:
                    pending = True
                    break
                if cost == float('inf') or existing-cost < w.config.depot_delivery_saving:
                    continue
                # At least two workers must have a real static route to legal work cells.
                approaches = sorted({q for cell in cells for q in neighbors(w.terrain, cell) if q not in cells})
                reachable = 0
                for worker in sorted(available, key=lambda a: (distance(a.position, p), a.id)):
                    route = nav.region_cost(('build', c.faction, p), approaches, worker.position)
                    if route is None:
                        pending = True
                        break
                    reachable += route != float('inf')
                    if reachable >= 2:
                        break
                if reachable < 2:
                    continue
                self.event('proposal', faction=c.faction, position=p, observed_source=source,
                           saved_distance=existing-cost)
                if c.faction not in self.savings:
                    self.savings[c.faction] = (p, w.turn+w.config.depot_savings_turns)
                floor = c.reserve_target if w.config.strategic_reserves_enabled and c.strategic_state != 'Total War' else 0
                if c.reserves < 15+floor:
                    self.failures['saving for construction'] += 1
                    return
                job = construction.create(c.faction, 'depot', p)
                if job is not None:
                    return
        self.failures['navigation pending' if pending else 'no beneficial legal site'] += 1

    def destination(self, ant):
        nav = self.world.navigation
        home = nav.home(ant.faction)
        candidates=[(min((distance(ant.position,p) for p in home),default=float('inf')),
                     -1,home,('home',ant.faction))]
        for d in self.world.depots:
            if d.faction==ant.faction and self.connected(d):
                candidates.append((min(distance(ant.position,p) for p in d.footprint),d.id,d.footprint,('depot',d.id)))
        options=[];pending=[];best=float('inf')
        for lower,ident,cells,key in sorted(candidates,key=lambda item:(item[0],item[1])):
            if lower>best:continue  # an exact known winner proves this candidate cannot improve
            cost=nav.region_cost(key,cells,ant.position)
            if cost is None:pending.append(lower)
            else:
                options.append((cost,ident,cells));best=min(best,cost)
        # An unfinished route cannot block a proven shortest endpoint. Equal-cost
        # unresolved candidates are unnecessary: any exact shortest tie is legal.
        if any(lower<best for lower in pending) or not options:
            ant.state,ant.target='delivery-plan',ant.position
            return True
        cost, ident, cells = min(options, default=(float('inf'), -1, ()), key=lambda v: (v[0], v[1]))
        # On equal costs, retain a valid destination; otherwise use exact cheapest cost.
        old = next((v for v in options if v[1] == ant.depot_id and v[0] == cost), None)
        if old is not None:
            cost, ident, cells = old
        if cost == float('inf') or not cells:
            ant.state, ant.target = 'delivery-plan', ant.position
            return True
        ant.depot_id = ident if ident >= 0 else None
        ant.state = 'deliver-depot' if ident >= 0 else 'return-base'
        ant.target = ant.position if ant.position in cells else cells[0]
        return True

    def prepare(self, ant):
        if self.world.colonies[ant.faction].alive and ant.kind == 'worker' and ant.cargo and ant.cargo_origin != 'ration':
            return self.destination(ant)
        return False

    def action(self, ant, turn):
        if ant.hp <= 0 or ant.action_used or ant.kind != 'worker' or not ant.cargo or ant.cargo_origin == 'ration':
            return False
        d = self.get(self.at_cell.get(ant.position), ant.faction)
        if d is None or not self.connected(d) or ant.state != 'deliver-depot' or ant.depot_id != d.id:
            return False
        c = self.world.colonies[d.faction]
        amount = ant.cargo
        ant.cargo = 0
        c.reserves += amount
        c.received_half += int(2*amount)
        d.deposited += amount
        self.world.food_system.delivered += amount
        ant.action_used, ant.last_action, ant.last_action_turn = True, 'deposit-food', turn
        return True
