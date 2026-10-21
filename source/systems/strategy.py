"""Allocation policy and local, one-hop-per-turn queen order communication."""
from collections import Counter
from math import ceil
from ai.pathfinding import distance
from simulation.spatial import SpatialIndex
from systems.perks import queen_sensing


def reserve_target(config, population):
    return max(config.strategic_reserve_min, ceil(config.strategic_reserve_per_ant*population))


def update_reserves(world):
    counts = Counter(a.faction for a in world.ants if a.hp > 0 and a.kind != 'honeypot')
    for colony in world.colonies:
        colony.reserve_target = reserve_target(world.config, counts[colony.faction]) if colony.alive else 0


class Orders:
    def __init__(self, world):
        self.world = world
        self.last_turn = -1
        self.received = 0
        self.logistics = set()

    def propagate(self, turn, index=None):
        if turn <= self.last_turn:
            return
        self.last_turn = turn
        ants = [a for a in self.world.ants if a.hp > 0]
        index = index if index is not None else SpatialIndex(ants)
        # Snapshot first: messages cannot traverse a whole chain within one tick.
        previous = {a.id: (a.order_epoch, a.order_state, a.order_target) for a in ants}
        for ant in ants:
            colony = self.world.colonies[ant.faction]
            if not colony.alive:
                ant.order_epoch, ant.order_state, ant.order_target = -1, 'Peace', None
                continue
            if ant.order_epoch == colony.declaration_epoch:
                continue  # no higher queen version can exist; knowledge content is not leaked
            message = previous[ant.id]
            if min(distance(ant.position, p) for p in colony.queen.footprint) <= queen_sensing(colony, self.world.config):
                message = (colony.declaration_epoch, colony.strategic_state, colony.declaration_target)
            for other in index.near(ant.position, self.world.config.communication_radius):
                if other.faction == ant.faction and previous[other.id][0] > message[0]:
                    message = previous[other.id]
            if message[0] > ant.order_epoch:
                ant.order_epoch, ant.order_state, ant.order_target = message
                self.received += 1
        information=getattr(self.world,'information',None)
        if information is not None:
            information.propagate(turn,index)
            for ant in ants:self.world.behavior.record(ant,turn)
        self.logistics.clear()
        workers = [[] for _ in self.world.colonies]
        for ant in ants:
            if ant.kind == 'worker':
                workers[ant.faction].append(ant)
        for members in workers:
            members.sort(key=lambda a: a.id)
            # Keep a limited but nonzero workforce gathering during mobilization.
            count = max(1, ceil(len(members)*self.world.config.war_logistics_fraction))
            self.logistics.update(a.id for a in members[:count])
