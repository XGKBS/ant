from collections import defaultdict
from ai.pathfinding import distance, neighbors
from ai.pheromones import BATTLE
from simulation.spatial import SpatialIndex

class Combat:
    def __init__(self, world, pheromones):
        self.world, self.pheromones = world, pheromones
        self.attacks = 0
        self.refresh()

    def refresh(self):
        self.index = SpatialIndex(self.world.ants)
        self.entities = {('ant', a.id): a for a in self.world.ants if a.hp > 0}
        self.entities.update({('queen', c.queen.id): c.queen for c in self.world.colonies if c.alive})

    def target_distance(self, position, key):
        entity = self.entities.get(key)
        if entity is None:
            return float('inf')
        return min(distance(position, p) for p in entity.footprint) if key[0] == 'queen' else distance(position, entity.position)

    def enemy(self, ant, radius):
        if not self.world.config.combat_enabled or ant.hp <= 0:
            return None
        choices = [('ant', a.id) for a in self.index.near(ant.position, radius) if a.faction != ant.faction]
        choices += [('queen', c.queen.id) for c in self.world.colonies if c.alive and c.faction != ant.faction
                    and min(distance(ant.position, p) for p in c.queen.footprint) <= radius]
        # Nearest target; ants before queens at equal distance, then stable entity ID.
        return min(choices, key=lambda k: (self.target_distance(ant.position, k), k)) if choices else None

    def approach(self, ant, key):
        entity = self.entities.get(key)
        if entity is None:
            return None
        if self.target_distance(ant.position, key) <= self.world.config.combat_range:
            return ant.position
        footprint = entity.footprint if key[0] == 'queen' else [entity.position]
        cells = {q for p in footprint for q in neighbors(self.world.terrain, p)}
        return min(cells, key=lambda p: (distance(ant.position, p), p)) if cells else None

    def resolve(self, turn):
        if not self.world.config.combat_enabled:
            return
        self.refresh()
        damage = defaultdict(int)
        for ant in self.world.ants:
            if ant.hp <= 0 or ant.action_used or ant.damage == 0:
                continue
            key = self.enemy(ant, self.world.config.combat_range)
            if key is None:
                continue
            ant.combat_target = key
            ant.state = 'fight'
            ant.action_used, ant.last_action, ant.last_action_turn = True, 'attack', turn
            damage[key] += ant.damage
            self.attacks += 1
            entity = self.entities[key]
            colony = self.world.colonies[entity.faction]
            colony.last_attacked_turn = turn
            colony.last_attack_position = entity.position
            if key[0] == 'queen':
                entity.last_attacked_turn = turn
            self.pheromones.reinforce(ant.faction, BATTLE, ant.position, 8)
            self.pheromones.reinforce(entity.faction, BATTLE, entity.position, 8)
        # Everyone alive at this action snapshot lands their one attack, even if killed.
        for key, amount in damage.items():
            self.entities[key].hp = max(0, self.entities[key].hp-amount)
