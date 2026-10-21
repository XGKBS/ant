"""Worker decisions consume local observations and remembered facts, never hidden food."""
from ai.pathfinding import distance, neighbors, route_step, find_path
from ai.pheromones import BASE, FOOD, BATTLE
from simulation.terrain import SOIL
from systems.perks import sensing, load

class WorkerFSM:
    def __init__(self, world, food, pheromones, combat=None, construction=None):
        self.world, self.food, self.pheromones = world, food, pheromones
        self.combat = combat
        self.construction = construction

    def base_cells(self, ant):
        if hasattr(self.world,'navigation'):
            return self.world.navigation.home(ant.faction)
        queen = self.world.colonies[ant.faction].queen
        return sorted({q for p in queen.footprint for q in neighbors(self.world.terrain, p)})

    def observe(self, ant):
        p = ant.position
        radius = sensing(ant, self.world.colonies[ant.faction])
        visible = self.food.visible(p, radius)
        ant.station_empty_until = {k:v for k,v in ant.station_empty_until.items() if v > self.world.turn}
        for station in self.world.stations:
            if distance(p, station.position) <= radius and station.units <= 0:
                ant.station_empty_until[station.id] = station.next_refill
                ant.known_food.pop(station.id, None)
        self.world.information.observe(ant, visible)
        for source in visible:
            ant.food_observations[source.id] = (source.position, source.units, source.tier, self.world.turn, (hasattr(source, "next_refill") or source.tier not in ("trophy", "drop") and (source.tier != "micro" or self.world.config.micro_respawn_tier is not None)))
            if source.id not in ant.ignored_food:
                ant.known_food[source.id] = source.position
        for food_id, target in list(ant.known_food.items()):
            if distance(p, target) <= radius and not any(f.id == food_id for f in visible):
                old = ant.food_observations.get(food_id)
                if old is not None:
                    self.world.information.publish(ant, "food", food_id, target, (0, old[2], old[4]))
                    ant.food_observations[food_id] = (target, 0, old[2], self.world.turn, old[4])
                ant.known_food.pop(food_id, None)
        limit=2*self.world.config.information_capacity
        while len(ant.known_food)>limit:ant.known_food.pop(next(iter(ant.known_food)))
        while len(ant.food_observations)>limit:ant.food_observations.pop(next(iter(ant.food_observations)))
        ant.foreign_target = self.pheromones.sense_foreign(ant.faction, p, radius)
        ant.foreign_signal = ant.foreign_target is not None
        if self.world.config.combat_enabled and ant.foreign_signal and p not in ant.reported_signals:
            ant.pending_report = ant.pending_report or ant.foreign_target
            ant.reported_signals.add(p)

    def public_station(self, ant):
        # Public coordinates only. Hidden stock is deliberately NOT inspected.
        nav=self.world.navigation
        candidates = [s for s in self.world.stations if s.id not in ant.station_empty_until and s.id not in ant.ignored_food
                      and self.world.terrain.capacity[s.position[1],s.position[0]]]
        if not candidates:
            return False
        current=next((s for s in candidates if s.id==ant.food_id),None)
        if current is not None and self.world.turn<ant.station_commit_until:
            s=current
        else:
            nav.metrics['station_evaluations']+=len(candidates)
            s = min(candidates,key=lambda s:(nav.station_cost(ant,s),s.id))
            if nav.station_cost(ant,s)==float('inf'):return False
            if current is not None and nav.station_cost(ant,current)<=nav.station_cost(ant,s)+3:s=current
        if ant.food_id!=s.id:
            if ant.food_id in nav.station_ids:nav.metrics['station_switches']+=1
            nav.station_assignments[(ant.faction,ant.food_id)]-=1
            nav.station_assignments[(ant.faction,s.id)]+=1
            ant.station_commit_until=self.world.turn+self.world.config.station_commit_turns
        ant.food_id, ant.target = s.id, s.position
        ant.state = ('gather' if ant.position == s.position else 'seek-food') if self.world.colonies[ant.faction].alive else 'forage-to-heal'
        return True

    def prepare(self, ant):
        if ant.kind == 'honeypot':
            self.observe(ant)
            self.world.honeypots.prepare(ant, self.combat)
            return
        ant.ignored_food = {k: v-1 for k, v in ant.ignored_food.items() if v > 1}
        self.observe(ant)
        self.world.depot_system.observe(ant)
        ant.dig_target = None
        ant.combat_target = None
        colony = self.world.colonies[ant.faction]
        enemy = self.combat.enemy(ant, sensing(ant, colony)) if self.combat else None
        if enemy is not None:
            self.world.information.observe(ant, (), enemy, self.combat)
            ant.combat_target = enemy
            ant.state = 'fight'
            ant.target = self.combat.approach(ant, enemy)
            return
        if (colony.alive and ant.order_state == 'Total War'
                and (ant.kind == 'soldier' or ant.id not in self.world.orders.logistics)
                and not (ant.kind == 'worker' and ant.cargo and ant.cargo_origin != 'ration')):
            if ant.kind == 'worker' and self.construction and self.construction.prepare_idle(ant):
                return
            if ant.order_target is not None:
                candidates = list(neighbors(self.world.terrain, ant.order_target))
                ant.state = 'offensive' if ant.kind == 'soldier' else 'war-support'
                ant.target = min(candidates, key=lambda p: (distance(ant.position, p), p)) if candidates else None
                return
        if (colony.alive and colony.threat in ('near-base', 'critical') and colony.threat_target is not None
                and not (ant.kind == 'worker' and ant.order_state == 'Total War' and ant.id in self.world.orders.logistics)):
            ant.state = 'defend'
            point = colony.threat_target
            candidates = list(neighbors(self.world.terrain, point))
            ant.target = min(candidates, key=lambda p: (distance(ant.position, p), p)) if candidates else None
            return
        if not colony.alive:
            if ant.hp < ant.max_hp:
                if ant.cargo:
                    ant.state, ant.target = 'forage-to-heal', ant.position
                    return
                if self.world.depot_system.prepare_healing(ant):
                    return
                if ant.known_food:
                    ant.food_id = min(ant.known_food, key=lambda k: (distance(ant.position, ant.known_food[k]), k))
                    ant.state, ant.target = 'forage-to-heal', ant.known_food[ant.food_id]
                    return
                if self.public_station(ant):
                    return
            ant.food_id, ant.target, ant.state = None, None, 'explore'
            if self.construction:
                self.construction.prepare_idle(ant)
            return
        if self.construction and self.construction.resume_depot(ant):
            return
        if self.world.honeypots.worker_target(ant):
            return
        if self.world.depot_system.prepare(ant):
            return
        if ant.kind == 'worker' and ant.pending_report is not None and not ant.cargo:
            bases = self.base_cells(ant)
            ant.state = 'return-report'
            ant.target = min(bases, key=lambda p: (distance(ant.position, p), p)) if bases else None
            return
        if ant.soil_cargo and (ant.cargo or ant.known_food) and ant.kind == 'worker':
            ant.state, ant.target = 'store-soil', ant.position
            return
        if (colony.reserves < 0 and ant.kind == 'worker' and not ant.cargo and not ant.soil_cargo
                and not ant.known_food and ant.construction_task is None and self.public_station(ant)):
            return  # Recovery precedes new idle work, not combat or active jobs.
        if self.world.exploration.prepare(ant):
            return
        if self.construction and not ant.cargo and (ant.kind == 'soldier' or not ant.known_food) and self.construction.prepare_idle(ant):
            return
        if ant.kind == 'soldier':
            ant.food_id, ant.target, ant.state = None, None, 'patrol'
            options = list(neighbors(self.world.terrain, ant.position))
            if options:
                q = max(options, key=lambda p: self.pheromones.read(ant.faction, BATTLE, p)-ant.trail_visits.get(p, 0))
                if self.pheromones.read(ant.faction, BATTLE, q)-ant.trail_visits.get(q, 0) > 0:
                    ant.state, ant.target = 'investigate', q
                elif ant.foreign_signal:
                    ant.state, ant.target = 'investigate', ant.foreign_target
            if ant.target is None:
                self.world.behavior.prepare(ant, soldier=True)
            return
        if ant.cargo and ant.cargo_origin != 'ration':
            ant.state = 'return-base'
            bases = self.base_cells(ant)
            ant.target = min(bases, key=lambda p: (distance(ant.position, p), p)) if bases else None
            return
        if ant.known_food:
            if all(k in self.world.navigation.station_ids for k in ant.known_food) and self.public_station(ant):
                return
            food_id = min(ant.known_food, key=lambda k: (distance(ant.position, ant.known_food[k]), k))
            ant.food_id, ant.target = food_id, ant.known_food[food_id]
            ant.state = 'gather' if ant.position == ant.target else 'seek-food'
        else:
            ant.food_id, ant.target = None, None
            ant.state = 'explore'
            if (not self.food.sample(ant.position) and not any(self.pheromones.read(ant.faction, FOOD,p) > self.world.config.pheromone_cutoff
                                                            for p in neighbors(self.world.terrain,ant.position))):
                if not self.public_station(ant):
                    self.world.behavior.prepare(ant)

    def choose(self, ant, position):
        if ant.kind == 'honeypot':
            return self.world.honeypots.step(ant, position)
        t = self.world.terrain
        if ant.state in ('guard','patrol-route','escort','frontier-local','patrol-hold','idle-wait','planning-wait'):
            return self.world.behavior.step(ant,position)
        options = list(neighbors(t, position))
        if not options or ant.dig_target is not None:
            return position
        if ant.target is not None:
            desired = route_step(self.world, ant, position, ant.target)
            if desired == position and ant.target != position:
                if ant.navigation_status == 'pending':
                    return position
                if self.construction:
                    self.construction.blocked_route(ant, position, ant.target)
                if ant.construction_task is not None:
                    return position
                if ant.state in ('central-expedition', 'frontier-explore'):
                    self.world.exploration.failure(ant)
                # A bounded search failure must not strand a worker indefinitely.
                if not ant.cargo and ant.food_id is not None:
                    ant.ignored_food[ant.food_id] = self.world.config.failed_target_cooldown
                    ant.known_food.pop(ant.food_id, None)
                goal = ant.target
                ant.state = 'return-base' if ant.cargo and ant.kind == 'worker' and self.world.colonies[ant.faction].alive else 'explore'
                ant.target = goal if ant.cargo else None
                available = [p for p in options if t.available(*p)]
                if available:
                    return min(available, key=lambda p: (ant.visits.get(p, 0) + (0.2*distance(p, goal) if ant.cargo else 0), p))
                return position
            # Own base trails choose between homeward alternatives; A* handles detours.
            if ant.cargo and ant.state == 'return-base':
                homeward = [p for p in options if distance(p, ant.target) < distance(position, ant.target)
                            and t.available(*p) and ant.trail_visits.get(p, 0) < 2]
                if homeward:
                    best = max(homeward, key=lambda p: self.pheromones.read(ant.faction, BASE, p))
                    if self.pheromones.read(ant.faction, BASE, best) > self.pheromones.read(ant.faction, BASE, desired) + 0.01:
                        desired = best
            return self._traffic(ant, position, desired)

        colony = self.world.colonies[ant.faction]
        foraging = (colony.alive and ant.kind == 'worker') or (not colony.alive and ant.hp < ant.max_hp)
        local = {position}
        frontier = {position}
        for _ in range(sensing(ant, colony)):
            frontier = {q for p in frontier for q in neighbors(t, p)} - local
            local.update(frontier)
        current = self.food.sample(position)
        strongest = max(local, key=lambda p: (self.food.sample(p), -distance(position, p), p))
        if foraging and self.food.sample(strongest) > current:
            ant.state, ant.target = ('seek-food' if colony.alive else 'forage-to-heal'), strongest
            return self._traffic(ant, position, route_step(self.world, ant, position, strongest))

        # A scout follows only its faction's food trail. Revisit penalty releases stale loops.
        def trail_score(p):
            return self.pheromones.read(ant.faction, FOOD, p) - 0.6*ant.trail_visits.get(p, 0)
        trail = max(options, key=lambda p: (trail_score(p), -ant.visits.get(p, 0), p))
        if foraging and trail_score(trail) > self.world.config.pheromone_cutoff:
            ant.state, ant.target = ('seek-food' if colony.alive else 'forage-to-heal'), trail
            return self._traffic(ant, position, trail)

        # Least-visited exploration is systematic coverage, with seeded tie breaking only.
        self.world.rng.shuffle(options)
        x, y = position
        options.sort(key=lambda p: (ant.visits.get(p, 0), 0 if (p[0]-x, p[1]-y) == ant.heading else 1))
        ant.state = 'patrol' if ant.kind == 'soldier' and colony.alive else 'explore'
        return self._traffic(ant, position, options[0])

    def _traffic(self, ant, position, desired):
        t = self.world.terrain
        if desired == position:
            return position
        x, y = desired
        congested = not t.available(x, y)
        busy = int(t.traffic[y, x]) >= self.world.config.busy_path_visits
        if t.cells[y,x]==SOIL and busy:
            self.world.information.publish(ant,'excavation',desired,desired,(self.world.config.busy_path_visits,1))
        if t.cells[y, x] == SOIL and (busy or (congested and ant.blocked_turns+1 >= self.world.config.congestion_turns)):
            ant.state, ant.dig_target = 'dig', desired
            return position
        if congested:
            # Try a bounded alternate route around occupied neighbors before waiting.
            if ant.target is not None:
                return self.world.navigation.congestion_step(ant,position,ant.target)
            return position
        return desired

    def resolve_action(self, ant, turn):
        if ant.kind == 'honeypot':
            self.world.honeypots.action(ant, turn)
            return
        if ant.hp <= 0 or ant.action_used:
            return
        colony = self.world.colonies[ant.faction]
        if not colony.alive and ant.hp < ant.max_hp:
            amount = min(1, ant.max_hp-ant.hp)
            eaten = 0
            if ant.cargo:
                eaten = min(amount, ant.cargo)
                ant.cargo -= eaten
            else:
                source = next(iter(self.food.visible(ant.position, 0)), None)
                eaten = self.food.harvest(source, turn, amount) or 0
            if eaten:
                ant.hp = min(ant.max_hp, ant.hp+eaten)
                self.food.eaten += eaten
                ant.last_action = 'eat'
        if ant.last_action is not None:
            pass
        elif self.world.honeypots.action(ant, turn):
            pass
        elif self.world.depot_system.action(ant, turn):
            pass
        elif ant.dig_target is not None and distance(ant.position, ant.dig_target) <= 1:
            if self.construction:
                self.construction.dig(ant, ant.dig_target, turn)
            elif self.world.terrain.dig(*ant.dig_target):
                ant.last_action = 'dig'
        elif self.construction and self.construction.action(ant, turn):
            pass
        elif colony.alive and ant.kind == 'worker' and ant.cargo and ant.cargo_origin != 'ration' and ant.position in self.base_cells(ant):
            colony.reserves = (colony.reserves_half + int(ant.cargo*2))/2
            colony.received_half += int(ant.cargo*2)
            self.food.delivered += ant.cargo
            ant.cargo = 0
            ant.cargo_origin = 'harvest'
            ant.last_action = 'deliver'
            ant.trail_visits.clear()
            if ant.pending_report is not None:
                colony.report_position, colony.report_turn = ant.pending_report, turn
                ant.pending_report = None
        elif colony.alive and ant.pending_report is not None and ant.position in self.base_cells(ant):
            colony.report_position, colony.report_turn = ant.pending_report, turn
            ant.pending_report = None
            ant.last_action = 'report'
        elif colony.alive and ant.kind == 'soldier' and ant.cargo+ant.soil_cargo < load(ant, colony):
            source = next(iter(self.food.visible(ant.position, 0)), None)
            amount = self.food.harvest(source, turn, load(ant, colony)-ant.cargo-ant.soil_cargo, ant=ant)
            if amount:
                ant.cargo += amount
                ant.cargo_origin = 'ration'
                ant.last_action = 'gather-ration'
        elif colony.alive and ant.kind == 'worker' and not ant.cargo:
            source = next((f for f in self.food.visible(ant.position, 0)
                           if not (ant.state in ('central-expedition', 'frontier-explore')
                                   and f.id in self.world.navigation.station_ids)), None)
            amount = self.food.harvest(source, turn, load(ant, colony)-ant.soil_cargo, ant=ant)
            if amount:
                ant.cargo, ant.food_id = amount, source.id
                ant.cargo_origin = 'harvest'
                ant.known_food[source.id] = source.position
                ant.food_distance = 0
                ant.trail_visits.clear()
                ant.state = 'gather'
                ant.last_action = 'gather'
        if ant.last_action:
            ant.action_used = True
            ant.last_action_turn = turn


