from simulation.world import World
from ai.pheromones import Pheromones, BASE, FOOD
from ai.pathfinding import distance
from ai.state_machine import WorkerFSM
from systems.food import FoodSystem
from systems.combat import Combat
from systems.lifecycle import Lifecycle
from systems.reproduction import Reproduction
from systems.perks import movement
from ai.colony_strategy import ColonyStrategy
from systems.construction import Construction
from systems.supply import Supply
from systems.economy import Economy
from ai.navigation import Navigation
from systems.strategy import Orders
from systems.depots import Depots
from systems.honeypots import Honeypots
from ai.exploration import Exploration
from systems.information import Information
from ai.behavior import Behavior

class Engine:
    """A turn resolves after its one-second animation interval completes."""
    def __init__(self, config):
        self.config = config
        self.speed = 1
        self.reset()

    def reset(self):
        self.world = World(self.config)
        self.turn = 0
        self.progress = 0.0
        self.paused = False
        self.ended = False
        self.outcome = ''
        self.winner = None
        self.max_turns = self.config.max_turns
        self.supply = Supply(self.world)
        self.economy = Economy(self.world)
        self.food = FoodSystem(self.world)
        self.world.food_system = self.food
        self.depots = self.world.depot_system = Depots(self.world)
        self.orders = self.world.orders = Orders(self.world)
        self.pheromones = Pheromones(self.config)
        self.combat = Combat(self.world, self.pheromones)
        self.lifecycle = Lifecycle(self.world, self.food)
        self.reproduction = Reproduction(self.world)
        self.strategy = ColonyStrategy(self.world, self.combat, self.pheromones)
        self.construction = Construction(self.world)
        self.navigation = self.world.navigation = Navigation(self.world)
        self.exploration = self.world.exploration = Exploration(self.world)
        self.information = self.world.information = Information(self.world)
        self.behavior = self.world.behavior = Behavior(self.world)
        self.honeypots = self.world.honeypots = Honeypots(self.world)
        self.fsm = WorkerFSM(self.world, self.food, self.pheromones, self.combat, self.construction)
        self._plan()

    def _plan(self):
        # Cardinal substeps use each ant's kind/perk budget and rotating priority.
        t = self.world.terrain
        self.navigation.begin_turn(self.turn)
        self.combat.refresh()
        self.strategy.assess(self.turn)
        self.behavior.begin_plan()
        self.information.index = self.combat.index
        self.exploration.begin_plan()
        self.honeypots.begin_plan(self.combat.index)
        self.depots.begin_plan()
        for ant in self.world.ants:
            ant.path = [ant.position]
            ant.planned_budget = movement(ant, self.world.colonies[ant.faction])
            self.fsm.prepare(ant)
        self.construction.begin_plan()
        count = len(self.world.ants)
        offset = self.turn % count if count else 0
        order = self.world.ants[offset:] + self.world.ants[:offset]
        for step in range(max((a.planned_budget for a in order), default=0)):
            for ant in order:
                if step >= ant.planned_budget:
                    continue
                x, y = ant.path[-1]
                target = (x, y)
                desired = self.fsm.choose(ant, (x, y))
                if desired != (x, y) and t.available(*desired):
                    target = desired
                    ant.heading = target[0]-x, target[1]-y
                    t.occupancy[y, x] -= 1
                    t.occupancy[target[1], target[0]] += 1
                    if ant.route and ant.route[0] == target:
                        ant.route.pop(0)
                ant.path.append(target)

    def _resolve(self):
        # Fixed ordering: movement, ecology, hunger, combat/deaths, other actions, economy.
        t = self.world.terrain
        self.world.turn = self.turn
        for ant in self.world.ants:
            ant.position = ant.path[-1]
            moved = any(a != b for a, b in zip(ant.path, ant.path[1:]))
            ant.moved_this_turn = moved
            ant.blocked_turns = 0 if moved else ant.blocked_turns + 1
            for previous, p in zip(ant.path, ant.path[1:]):
                ant.visits[p] = ant.visits.get(p, 0) + 1
                ant.trail_visits[p] = ant.trail_visits.get(p, 0) + 1
                if previous != p:
                    t.traffic[p[1], p[0]] += 1
        self.food.tick(self.turn)
        self.supply.tick(self.turn)
        self.pheromones.decay()
        for ant in self.world.ants:
            ant.action_used, ant.last_action = False, None
        self.lifecycle.hunger(self.turn)
        self.lifecycle.cleanup(self.turn)
        self.combat.resolve(self.turn)
        self.lifecycle.cleanup(self.turn)
        self.construction.resolve(self.turn)
        for ant in self.world.ants:
            carried = bool(ant.cargo)
            self.fsm.resolve_action(ant, self.turn)
            queen = self.world.colonies[ant.faction].queen
            for p in ant.path:
                if self.world.colonies[ant.faction].alive:
                    dx,dy=p[0]-queen.position[0],p[1]-queen.position[1]
                    base_distance=(-dx if dx<0 else dx-1 if dx>1 else 0)+(-dy if dy<0 else dy-1 if dy>1 else 0)
                    self.pheromones.reinforce(ant.faction, BASE, p, 8/(1+0.1*base_distance))
                if ant.kind == 'worker' and (carried or ant.last_action == 'gather'):
                    self.pheromones.reinforce(ant.faction, FOOD, p, 8/(1+0.1*ant.food_distance))
                    ant.food_distance += 1
        self.combat.refresh()
        self.strategy.assess(self.turn)
        self.orders.propagate(self.turn, self.combat.index)
        self.reproduction.tick(self.turn)
        self.economy.tick(self.turn)
        self.lifecycle.cleanup(self.turn)
        self.food.rebuild_scent()

    def display_position(self, ant):
        segments = len(ant.path)-1
        if segments <= 0:
            return ant.position
        phase = min(self.progress * segments, segments)
        i = min(int(phase), segments-1)
        fraction = phase - i
        a, b = ant.path[i], ant.path[i+1]
        return tuple(a[j] + (b[j]-a[j])*fraction for j in range(2))

    def advance(self, seconds, max_ticks=None):
        if seconds < 0:
            raise ValueError('Elapsed time cannot be negative')
        if max_ticks is not None and max_ticks < 1:
            raise ValueError('Tick work budget must be positive')
        if self.paused or self.ended:
            return
        self.progress += seconds * self.speed
        processed = 0
        while self.progress + 1e-10 >= 1 and not self.ended and (max_ticks is None or processed < max_ticks):
            processed += 1
            self.progress = max(0.0, self.progress - 1)
            self.turn += 1
            self._resolve()
            self.winner = self.lifecycle.winner()
            if self.winner is not None or self.lifecycle.all_queens_dead():
                self.progress = 1.0
                self.end(f'{("Red", "Yellow", "Blue", "Green")[self.winner]} wins: last surviving queen' if self.winner is not None else 'No winner: all queens died simultaneously')
            elif self.max_turns is not None and self.turn >= self.max_turns:
                self.progress = 1.0
                self.end('Turn limit: no winner (multiple queens alive)')
            else:
                self._plan()

    def end(self, reason='Manually ended: no winner'):
        if self.ended:
            return
        self.ended = True
        self.outcome = reason

    def finish_limit(self):
        self.winner = self.lifecycle.winner()
        if self.winner is not None:
            self.end(f'{("Red", "Yellow", "Blue", "Green")[self.winner]} wins: last surviving queen')
        elif self.lifecycle.all_queens_dead():
            self.end('No winner: all queens died simultaneously')
        else:
            self.end('Turn limit: no winner (multiple queens alive)')
