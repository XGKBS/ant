import unittest
import numpy as np
from config import Config
from simulation.engine import Engine
from simulation.terrain import Terrain, SOIL, PASSAGE, STONE

class FoundationTests(unittest.TestCase):
    def make(self, **kwargs):
        return Engine(Config(size=32, reproduction_enabled=False, combat_enabled=False, perks=('production',)*4, **kwargs))

    def test_four_colonies(self):
        e = self.make()
        self.assertEqual(len(e.world.colonies), 4)
        self.assertEqual(len(e.world.ants), 8)
        cells = set()
        for c in e.world.colonies:
            self.assertEqual(len(c.queen.footprint), 4)
            cells.update(c.queen.footprint)
            self.assertEqual(sum(a.faction == c.faction for a in e.world.ants), 2)
        self.assertEqual(len(cells), 16)

    def test_capacity_and_dig(self):
        t = Terrain(4)
        t.occupancy[1, 1] = 1
        self.assertFalse(t.available(1, 1))
        self.assertTrue(t.dig(1, 1))
        self.assertEqual(t.capacity[1, 1], 4)
        self.assertEqual(t.excavated_units, 1)
        self.assertFalse(t.dig(1, 1))
        t.occupancy[1, 1] = 4
        self.assertFalse(t.available(1, 1))
        t.set(2, 2, STONE)
        self.assertFalse(t.available(2, 2))

    def test_traffic_and_movement_budget(self):
        e = self.make()
        for _ in range(200):
            t = e.world.terrain
            counts = np.zeros_like(t.occupancy)
            for ant in e.world.ants:
                self.assertEqual(ant.path[0], ant.position)
                for a, b in zip(ant.path, ant.path[1:]):
                    self.assertLessEqual(abs(a[0]-b[0])+abs(a[1]-b[1]), 1)
                counts[ant.path[-1][1], ant.path[-1][0]] += 1
            np.testing.assert_array_equal(counts, t.occupancy)
            self.assertTrue(np.all(t.occupancy <= t.capacity))
            e.advance(1)

    def test_speeds_and_frame_independence(self):
        for speed in (1, 2, 4, 8):
            e = self.make()
            e.speed = speed
            for _ in range(60):
                e.advance(1/60)
            self.assertEqual(e.turn, speed)
        a, b = self.make(), self.make()
        a.advance(10.25)
        for _ in range(41):
            b.advance(0.25)
        self.assertEqual(a.turn, b.turn)
        self.assertEqual([x.path for x in a.world.ants], [x.path for x in b.world.ants])

    def test_pause_end_reset_and_limit(self):
        e = self.make(max_turns=3)
        e.advance(0.25)
        positions = [e.display_position(a) for a in e.world.ants]
        e.paused = True
        e.advance(20)
        self.assertEqual(e.turn, 0)
        self.assertEqual(positions, [e.display_position(a) for a in e.world.ants])
        e.paused = False
        e.advance(20)
        self.assertEqual(e.turn, 3)
        self.assertTrue(e.ended)
        e.advance(10)
        self.assertEqual(e.turn, 3)
        e.reset()
        self.assertEqual(e.turn, 0)
        self.assertFalse(e.ended)
        e.end()
        e.advance(4)
        self.assertEqual(e.turn, 0)

    def test_food_spacing_and_reproducibility(self):
        a, b = self.make(), self.make()
        self.assertEqual(a.world.food, b.world.food)
        self.assertEqual(len(a.world.food), 24)
        for i, food in enumerate(a.world.food):
            x, y = food.position
            self.assertGreater(a.world.terrain.capacity[y, x], 0)
            for other in a.world.food[i+1:]:
                self.assertGreaterEqual((x-other.position[0])**2+(y-other.position[1])**2, 25)

    def test_validation(self):
        for kwargs in ({'size': 10}, {'max_turns': 0}, {'max_turns': -1}):
            with self.assertRaises(ValueError):
                Config(**kwargs)

    def test_interpolation_and_blocked_wait(self):
        e = self.make()
        ant = e.world.ants[0]
        a, b = ant.path[:2]
        e.advance(0.25)
        self.assertEqual(e.display_position(ant), ((a[0]+b[0])/2, (a[1]+b[1])/2))
        queens = [c.queen.position for c in e.world.colonies]
        e.advance(10)
        self.assertEqual(queens, [c.queen.position for c in e.world.colonies])
        # Block every currently empty cell: each ant must keep both substeps in place.
        t = e.world.terrain
        t.capacity[:] = 0
        t.occupancy[:] = 0
        for worker in e.world.ants:
            x, y = worker.position
            t.capacity[y, x] = 1
            t.occupancy[y, x] = 1
        e._plan()
        for worker in e.world.ants:
            self.assertEqual(worker.path, [worker.position]*3)

if __name__ == '__main__':
    unittest.main()
