"""Footprint-aware stone geometry. No ant, rendering or RNG side effects."""
from dataclasses import dataclass
from fractions import Fraction
import numpy as np
from simulation.terrain import SOIL, PASSAGE, STONE, LARGE_STONE, NEST, REINFORCED

CARDINAL = ((1, 0), (0, 1), (-1, 0), (0, -1))

@dataclass
class Stone:
    id: int
    cells: tuple
    weight: int
    kind: int = STONE
    bound_soil: int = 0

def speed_ratio(capacity, weight, config):
    """Below half load: immovable; half load: 1/4; full load: 1.

    Rational interpolation avoids accumulating floating-point work drift.
    Configuration may change the two breakpoints explicitly.
    """
    ratio = Fraction(str(capacity))/Fraction(str(weight))
    minimum = Fraction(str(config.stone_min_load_ratio))
    slow = Fraction(str(config.stone_min_speed_ratio))
    if ratio < minimum:
        return Fraction(0)
    if ratio >= 1:
        return Fraction(1)
    return slow + (1-slow)*(ratio-minimum)/(1-minimum)

class Stones:
    def __init__(self, world):
        self.world = world
        self.groups = {}
        self.next_id = 0  # separate namespace; never consumes ant/food IDs
        t = world.terrain
        # One initialization scan. Ordinary stones are individual; touching large
        # patches form a single rigid footprint, preserving the original map mask.
        for y, x in np.argwhere(t.cells == STONE):
            self.register(((int(x), int(y)),), world.config.ordinary_stone_weight, STONE)
        remaining = {(int(x), int(y)) for y, x in np.argwhere(t.cells == LARGE_STONE)}
        while remaining:
            first = min(remaining)
            remaining.remove(first)
            component, frontier = [first], [first]
            while frontier:
                x, y = frontier.pop()
                for dx, dy in CARDINAL:
                    q = x+dx, y+dy
                    if q in remaining:
                        remaining.remove(q)
                        component.append(q)
                        frontier.append(q)
            self.register(component, len(component)*world.config.large_stone_weight_per_cell, LARGE_STONE)

    def register(self, cells, weight, kind=STONE):
        cells = tuple(sorted(set(cells)))
        t = self.world.terrain
        if not cells or weight <= 0 or any(not self.in_bounds(p) or t.stone_ids[p[1], p[0]] >= 0
                                            or t.occupancy[p[1], p[0]] or t.cells[p[1], p[0]] in (NEST, REINFORCED)
                                            or p in self.world.structure_cells or p in self.world.depot_claims
                                             or t.loose_soil.get(p) or any(f.position == p for f in (*self.world.food, *self.world.stations))
                                            for p in cells):
            raise ValueError('Invalid initial stone footprint')
        stone = Stone(self.next_id, cells, weight, kind)
        self.next_id += 1
        self.groups[stone.id] = stone
        for x, y in cells:
            t.stone_ids[y, x] = stone.id
            t.set(x, y, kind)
        return stone

    def in_bounds(self, p):
        h, w = self.world.terrain.cells.shape
        return 0 <= p[0] < w and 0 <= p[1] < h

    def destination(self, stone, direction):
        dx, dy = direction
        return tuple((x+dx, y+dy) for x, y in stone.cells)

    def can_move(self, stone, direction):
        if direction not in CARDINAL or self.groups.get(stone.id) is not stone:
            return False
        t = self.world.terrain
        food_sites = {f.position for f in (*self.world.food, *self.world.stations)}  # source count, never map area
        for x, y in self.destination(stone, direction):
            if not self.in_bounds((x, y)):
                return False
            owner = int(t.stone_ids[y, x])
            if t.occupancy[y, x]:
                return False
            if owner == stone.id:
                continue
            if (owner >= 0 or t.cells[y, x] not in (SOIL, PASSAGE)
                    or t.occupancy[y, x] or (x, y) in food_sites or t.loose_soil.get((x, y), 0)
                    or (x, y) in self.world.construction_sites or (x, y) in self.world.structure_cells
                    or (x, y) in self.world.depot_claims):
                return False
        return True

    def move(self, stone, direction):
        if not self.can_move(stone, direction):
            return False
        t = self.world.terrain
        new = self.destination(stone, direction)
        # All geometry and occupancy checks complete before the first write.
        for x, y in stone.cells:
            t.stone_ids[y, x] = -1
            t.set(x, y, SOIL if t.layers[y, x] else PASSAGE)
        for x, y in new:
            t.stone_ids[y, x] = stone.id
            t.set(x, y, stone.kind)
        stone.cells = tuple(sorted(new))
        return True

    def seam(self, first, second):
        other = set(second.cells)
        edges = sum((x+dx, y+dy) in other for x, y in first.cells for dx, dy in CARDINAL)
        return edges >= self.world.config.composition_min_shared_edges

    def can_compose(self, ids):
        if len(set(ids)) != 2 or any(i not in self.groups for i in ids):
            return False
        a, b = (self.groups[i] for i in ids)
        return len(a.cells)+len(b.cells) <= self.world.config.composition_max_cells and self.seam(a, b)

    def compose(self, job):
        ids, soil = job.stones, job.soil
        if soil != self.world.config.composition_soil or not self.can_compose(ids):
            return None
        a, b = (self.groups[i] for i in ids)
        # Union only: no new occupied cells, holes, rotation, or overwritten terrain.
        a.cells = tuple(sorted(a.cells+b.cells))
        a.weight += b.weight
        a.bound_soil += b.bound_soil+soil
        job.soil = 0
        a.kind = LARGE_STONE
        del self.groups[b.id]
        t = self.world.terrain
        for x, y in a.cells:
            t.stone_ids[y, x] = a.id
            t.set(x, y, a.kind)
        return a
