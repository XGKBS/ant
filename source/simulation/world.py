import random
from collections import deque
from entities.models import Ant, Queen, Colony, Food
from simulation.terrain import Terrain, SOIL, STONE, LARGE_STONE, NEST

DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))

class World:
    def __init__(self, config):
        self.config = config
        self.turn = 0
        self.rng = random.Random(config.seed)
        self.terrain = Terrain(config.size)
        self.colonies, self.ants, self.food = [], [], []
        n = config.size
        for y in range(n):
            for x in range(n):
                if self.rng.random() < config.stone_density:
                    self.terrain.set(x, y, STONE)
        for y in range(n - 1):
            for x in range(n - 1):
                if self.rng.random() < config.large_stone_density:
                    for dy in range(2):
                        for dx in range(2):
                            self.terrain.set(x + dx, y + dy, LARGE_STONE)
        for faction, (x, y) in enumerate(((2, 2), (n-4, 2), (2, n-4), (n-4, n-4))):
            for cy in range(max(0, y-config.nest_clearance), min(n, y+2+config.nest_clearance)):
                for cx in range(max(0, x-config.nest_clearance), min(n, x+2+config.nest_clearance)):
                    self.terrain.set(cx, cy, SOIL)
            queen = Queen(faction, faction, (x, y))
            self.colonies.append(Colony(faction, queen, perk=config.perks[faction]))
            for cx, cy in queen.footprint:
                self.terrain.set(cx, cy, NEST)
            for pos in ((x-1, y), (x-1, y+1)):
                ant = Ant(4 + len(self.ants), faction, pos, heading=self.rng.choice(DIRECTIONS))
                ant.path = [pos, pos, pos]
                self.ants.append(ant)
                self.terrain.occupancy[pos[1], pos[0]] += 1
        # Flood fill from all nests: food must be in an actually reachable component.
        reachable = set(a.position for a in self.ants)
        queue = deque(reachable)
        while queue:
            x, y = queue.popleft()
            for dx, dy in DIRECTIONS:
                p = x+dx, y+dy
                if 0 <= p[0] < n and 0 <= p[1] < n and self.terrain.capacity[p[1], p[0]] and p not in reachable:
                    reachable.add(p)
                    queue.append(p)
        candidates = sorted(reachable)
        self.rng.shuffle(candidates)
        self.food_candidates = candidates
        tiers = (('micro', 1, 2), ('small', 5, 4), ('medium', 10, 8), ('large', 25, 16))
        for p in candidates:
            if len(self.food) >= config.food_count:
                break
            if all((p[0]-f.position[0])**2 + (p[1]-f.position[1])**2 >= config.food_spacing**2 for f in self.food):
                tier, units, radius = tiers[len(self.food) % 4]
                self.food.append(Food(12 + len(self.food), p, tier, units, radius))
                if len(self.food) == config.food_count:
                    break
        if len(self.food) != config.food_count:
            raise ValueError('Cannot place requested food sources with five-cell spacing')
        self.next_food_id = 12 + len(self.food)
        from systems.supply import create_stations
        self.stations = create_stations(self) if config.supply_stations_enabled else []
        self.station_locations = tuple(s.position for s in self.stations)

    def allocate_id(self):
        entity_id = self.next_food_id
        self.next_food_id += 1
        return entity_id
