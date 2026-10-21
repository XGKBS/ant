import unittest
import numpy as np
from config import Config
from entities.models import Food
from simulation.engine import Engine
from simulation.terrain import SOIL, STONE, PASSAGE
from ai.pheromones import Pheromones, BASE, FOOD
from ai.pathfinding import find_path

def fixture(size=32):
    # Isolate the original closed ordinary-food interval from Phase 4E sources/sinks.
    e = Engine(Config(size=size, supply_stations_enabled=False, colony_economy_enabled=False, food_count=0, stone_density=0, large_stone_density=0, reproduction_enabled=False, combat_enabled=False, perks=('production',)*4))
    return e

def replan(e):
    t = e.world.terrain
    t.occupancy[:] = 0
    for ant in e.world.ants:
        ant.route.clear()
        t.occupancy[ant.position[1], ant.position[0]] += 1
    e.food.rebuild_scent()
    e._plan()

class ResourceTests(unittest.TestCase):
    def test_scent_expansion_intensity_and_obstacles(self):
        e = fixture()
        food = Food(100, (15, 15), 'medium', 10, 8)
        e.world.food = [food]
        e.food.rebuild_scent()
        self.assertEqual(e.food.sample((15, 15)), 1)
        self.assertEqual(e.food.sample((16, 15)), 0)
        for turn in range(1, 11):
            e.food.tick(turn)
            e.food.rebuild_scent()
            radius = min(turn, 8)
            self.assertGreater(e.food.sample((15+radius, 15)), 0)
            self.assertEqual(e.food.sample((16+radius, 15)), 0)
        self.assertGreater(e.food.sample((16, 15)), e.food.sample((20, 15)))
        e.world.terrain.set(16, 15, STONE)
        e.food.rebuild_scent()
        self.assertEqual(e.food.sample((16, 15)), 0)
        food.units = 0
        e.food.rebuild_scent()
        self.assertEqual(e.food.sample(food.position), 0)

    def test_pickup_delivery_own_queen_and_conservation(self):
        e = fixture()
        e.world.food = [Food(100, (7, 2), 'small', 5, 4, age=4)]
        e.world.ants = e.world.ants[:2]
        replan(e)
        actions, states = set(), set()
        for _ in range(24):
            e.advance(1)
            for ant in e.world.ants:
                states.add(ant.state)
                if ant.last_action:
                    actions.add(ant.last_action)
                    self.assertEqual(ant.last_action_turn, e.turn)
                self.assertLessEqual(ant.cargo, 1)
            self.assertEqual(5, e.world.food[0].units + sum(a.cargo for a in e.world.ants) + sum(c.reserves for c in e.world.colonies))
        self.assertIn('gather', actions)
        self.assertIn('deliver', actions)
        self.assertIn('return-base', states)
        self.assertGreater(e.world.colonies[0].reserves, 0)
        self.assertEqual([c.reserves for c in e.world.colonies[1:]], [0, 0, 0])

    def test_scent_navigation_without_food_memory(self):
        e = fixture()
        ant = e.world.ants[0]
        ant.position = (10, 15)
        e.world.food = [Food(100, (17, 15), 'medium', 10, 8, age=8)]
        replan(e)
        self.assertFalse(ant.known_food)
        self.assertEqual(ant.state, 'seek-food')
        self.assertGreater(ant.path[-1][0], 10)

    def test_pheromone_decay_reinforcement_and_faction_isolation(self):
        p = Pheromones(Config(size=32))
        p.reinforce(0, FOOD, (10, 10), 4)
        first = p.read(0, FOOD, (10, 10))
        p.decay()
        self.assertAlmostEqual(p.read(0, FOOD, (10, 10)), first*0.96, places=5)
        p.reinforce(0, FOOD, (10, 10), 4)
        self.assertGreater(p.read(0, FOOD, (10, 10)), first)
        self.assertEqual(p.read(1, FOOD, (10, 10)), 0)
        self.assertTrue(p.foreign_presence(1, (10, 10)))
        for _ in range(200):
            p.decay()
        self.assertEqual(p.read(0, FOOD, (10, 10)), 0)
        self.assertFalse(p.active)

    def test_actual_food_trail_navigation_and_foreign_detection(self):
        e = fixture()
        ant = e.world.ants[0]
        ant.position = (10, 10)
        ant.heading = (-1, 0)
        e.pheromones.reinforce(0, FOOD, (11, 10), 6)
        e.pheromones.reinforce(1, FOOD, (9, 10), 20)
        replan(e)
        self.assertEqual(ant.path[1], (11, 10))
        self.assertEqual(ant.state, 'seek-food')
        self.assertTrue(ant.foreign_signal)

    def test_base_trail_navigation(self):
        e = fixture()
        ant = e.world.ants[0]
        ant.position, ant.cargo = (10, 10), 1
        # Both west and north approach home; own base scent selects north.
        e.pheromones.reinforce(0, BASE, (10, 9), 15)
        replan(e)
        self.assertEqual(ant.path[1], (10, 9))

    def test_depletion_downgrade_deadline_and_micro_default(self):
        for tier, units, radius, expected in [('large', 1, 16, 'medium'), ('medium', 1, 8, 'small'), ('small', 1, 4, 'micro'), ('micro', 1, 2, 'micro')]:
            e = fixture()
            f = Food(100, (15, 15), tier, units, radius)
            e.world.food = [f]
            self.assertTrue(e.food.harvest(f, 3))
            self.assertFalse(e.food.harvest(f, 3))
            self.assertEqual(f.respawn_deadline, 28)
            e.food.tick(27)
            self.assertEqual(f.units, 0)
            e.food.tick(28)
            self.assertEqual(f.tier, expected)
            self.assertGreater(f.units, 0)
            self.assertEqual(f.age, 0)
            self.assertIsNone(f.respawn_deadline)

    def test_periodic_generation_spacing_and_center(self):
        e = fixture(128)
        for turn in range(1, 301):
            e.food.tick(turn)
        self.assertEqual(sum(f.tier == 'small' for f in e.world.food), 24)
        self.assertEqual(sum(f.tier == 'medium' for f in e.world.food), 8)
        self.assertEqual(sum(f.tier == 'large' for f in e.world.food), 3)
        self.assertEqual(len({f.id for f in e.world.food}), 35)
        self.assertFalse(e.food.pending)
        for i, f in enumerate(e.world.food):
            if f.tier == 'large':
                self.assertLessEqual((f.position[0]-63.5)**2+(f.position[1]-63.5)**2, 21**2)
            for g in e.world.food[i+1:]:
                self.assertGreaterEqual(sum((a-b)**2 for a, b in zip(f.position, g.position)), 25)

    def test_congestion_dig_and_single_action(self):
        e = fixture()
        e.world.ants = e.world.ants[:2]
        a, b = e.world.ants
        a.position, b.position = (10, 10), (11, 10)
        e.world.terrain.capacity[:] = 0
        for x in range(10, 13):
            e.world.terrain.set(x, 10, SOIL)
        a.blocked_turns = 1
        e.world.food = [Food(100, (12, 10), 'small', 5, 4, age=4)]
        replan(e)
        self.assertEqual(a.state, 'dig')
        self.assertEqual(a.dig_target, (11, 10))
        units = e.world.food[0].units
        e.advance(1)
        self.assertEqual(e.world.terrain.cells[10, 11], PASSAGE)
        self.assertEqual(e.world.terrain.capacity[10, 11], 4)
        self.assertEqual(a.last_action, 'dig')
        self.assertEqual(a.cargo, 0)
        self.assertEqual(e.world.terrain.excavated_units, 1)
        self.assertGreaterEqual(e.world.food[0].units, units-1)

    def test_busy_route_widens_and_capacity_stays_valid(self):
        e = fixture()
        ant = e.world.ants[0]
        e.world.ants = [ant]
        ant.position = (10, 10)
        e.world.food = [Food(100, (12, 10), 'small', 5, 4, age=4)]
        e.world.terrain.traffic[10, 11] = e.config.busy_path_visits
        replan(e)
        e.advance(1)
        self.assertEqual(ant.last_action, 'dig')
        self.assertEqual(e.world.terrain.capacity[10, 11], 4)
        for _ in range(100):
            e.advance(1)
            self.assertTrue(np.all(e.world.terrain.occupancy <= e.world.terrain.capacity))

    def test_bounded_pathfinding_avoids_stone(self):
        e = fixture()
        e.world.terrain.set(11, 10, STONE)
        path = find_path(e.world.terrain, (10, 10), (12, 10))
        self.assertEqual(path[-1], (12, 10))
        self.assertNotIn((11, 10), path)
        self.assertEqual(find_path(e.world.terrain, (10, 10), (20, 20), limit=1), [])

    def test_unreachable_food_does_not_freeze_worker(self):
        e = fixture()
        ant = e.world.ants[0]
        ant.position = (10, 10)
        e.world.ants = [ant]
        e.world.food = [Food(100, (12, 10), 'small', 5, 4, age=4)]
        for y in range(32):
            e.world.terrain.set(11, y, STONE)
        replan(e)
        self.assertNotEqual(ant.path[-1], ant.position)
        self.assertIn(100, ant.ignored_food)

    def test_saturated_map_queues_generation_without_overlap(self):
        e = Engine(Config(size=32, food_count=0, food_spacing=100))
        e.food.tick(50)
        self.assertEqual(len(e.world.food), 1)
        self.assertEqual(len(e.food.pending), 3)
        e.food.tick(75)
        self.assertEqual(len(e.world.food), 1)
        self.assertEqual(len(e.food.pending), 5)

    def test_real_delivery_reinforces_base_and_food_trails(self):
        e = fixture()
        ant = e.world.ants[0]
        ant.position = (5, 2)
        e.world.ants = [ant]
        e.world.food = [Food(100, (7, 2), 'small', 5, 4, age=4)]
        replan(e)
        for _ in range(20):
            e.advance(1)
            if e.food.delivered:
                break
        self.assertGreater(e.food.delivered, 0)
        self.assertGreater(e.pheromones.read(0, FOOD, (7, 2)), 0)
        self.assertGreater(e.pheromones.read(0, BASE, (5, 2)), 0)
        self.assertEqual(e.pheromones.read(1, FOOD, (7, 2)), 0)

    def test_resource_frame_independence_and_pause(self):
        a, b = fixture(), fixture()
        for e in (a, b):
            e.world.food = [Food(100, (7, 2), 'small', 5, 4, age=4)]
            replan(e)
        a.advance(125.25)
        for _ in range(501):
            b.advance(0.25)
        self.assertEqual(a.world.food, b.world.food)
        self.assertEqual([c.reserves for c in a.world.colonies], [c.reserves for c in b.world.colonies])
        np.testing.assert_array_equal(a.pheromones.values, b.pheromones.values)
        snapshot = a.pheromones.values.copy()
        ages = [f.age for f in a.world.food]
        a.paused = True
        a.advance(100)
        np.testing.assert_array_equal(snapshot, a.pheromones.values)
        self.assertEqual(ages, [f.age for f in a.world.food])

    def test_default_four_faction_autonomous_delivery(self):
        e = Engine(Config(size=64, reproduction_enabled=False, combat_enabled=False, perks=('production',)*4))
        for _ in range(300):
            e.advance(1)
            self.assertTrue(np.all(e.world.terrain.occupancy <= e.world.terrain.capacity))
        self.assertTrue(all(c.reserves > 0 for c in e.world.colonies))
        self.assertEqual(len(e.world.ants), 8)
        self.assertGreater(e.world.terrain.excavated_units, 0)

    def test_micro_retirement_policy(self):
        e = Engine(Config(size=32, food_count=0, micro_respawn_tier=None))
        f = Food(100, (15, 15), 'micro', 1, 2)
        e.world.food = [f]
        e.food.harvest(f, 1)
        e.food.tick(26)
        self.assertEqual(f.units, 0)
        self.assertIsNone(f.respawn_deadline)
