import random
import copy
import unittest
import numpy as np
from ai.pathfinding import find_path, route_step
from simulation.terrain import Terrain, SOIL, PASSAGE, STONE
from config import Config
from simulation.engine import Engine
from entities.models import Food
from tests.reference_pathfinding import reference_search
from benchmarks.compare_phase4a import compare

class SearchRegressionTests(unittest.TestCase):
    def test_workspace_rebuilds_for_a_different_array_shape(self):
        terrain = Terrain(8)
        find_path(terrain, (0, 0), (7, 7))
        workspace = terrain._search_workspace
        terrain.capacity = np.ones((12, 10), dtype=np.uint8)
        terrain.occupancy = np.zeros_like(terrain.capacity)
        self.assertEqual(find_path(terrain, (0, 0), (9, 11)), reference_search(terrain, (0, 0), (9, 11)))
        self.assertIsNot(workspace, terrain._search_workspace)

    def test_long_search_reused_workspace_reads_current_world(self):
        terrain = Terrain(64)
        start, goal = (1, 1), (60, 60)
        for iteration in range(8):
            terrain.occupancy[10+iteration, 10+iteration] = 1
            terrain.set(20+iteration, 20, STONE)
            avoid = {(30, 29+iteration)}
            self.assertEqual(find_path(terrain, start, goal, 4096, avoid), reference_search(terrain, start, goal, 4096, avoid))
        workspace = terrain._search_workspace
        self.assertIs(workspace, terrain._search_workspace)
        workspace.generation = 2**64-1
        self.assertEqual(find_path(terrain, start, goal), reference_search(terrain, start, goal))
        for x in range(20):
            target = (40+x, 60)
            self.assertEqual(find_path(terrain, start, target), reference_search(terrain, start, target))
        self.assertIs(workspace, terrain._search_workspace)

    def test_exact_phase3_routes_on_random_crowding_and_obstacles(self):
        for seed in range(12):
            rng = random.Random(seed)
            terrain = Terrain(24)
            for y in range(24):
                for x in range(24):
                    terrain.set(x, y, rng.choices([SOIL, PASSAGE, STONE], [7, 2, 1])[0])
                    terrain.occupancy[y, x] = rng.randrange(int(terrain.capacity[y, x])+1)
            for _ in range(20):
                start = rng.randrange(24), rng.randrange(24)
                goal = rng.randrange(24), rng.randrange(24)
                avoid = frozenset((rng.randrange(24), rng.randrange(24)) for _ in range(4))
                limit = rng.choice([1, 17, 100, 4096])
                self.assertEqual(find_path(terrain, start, goal, limit, avoid),
                                 reference_search(terrain, start, goal, limit, avoid), (seed, start, goal, limit))

    def test_reused_workspace_sees_occupancy_and_capacity_changes(self):
        terrain = Terrain(16)
        start, goal = (1, 1), (12, 1)
        self.assertEqual(find_path(terrain, start, goal), reference_search(terrain, start, goal))
        workspace = terrain._search_workspace
        terrain.occupancy[1, 5] = 1
        self.assertEqual(find_path(terrain, start, goal), reference_search(terrain, start, goal))
        terrain.dig(5, 1)
        self.assertEqual(find_path(terrain, start, goal), reference_search(terrain, start, goal))
        terrain.set(6, 1, STONE)
        self.assertEqual(find_path(terrain, start, goal), reference_search(terrain, start, goal))
        self.assertIs(workspace, terrain._search_workspace)

    def test_generation_wrap_and_failed_search_do_not_leak_costs(self):
        terrain = Terrain(16)
        self.assertEqual(find_path(terrain, (0, 0), (15, 15), 1), [])
        terrain._search_workspace.generation = 2**64-1
        self.assertEqual(find_path(terrain, (0, 0), (15, 15)), reference_search(terrain, (0, 0), (15, 15)))
        self.assertEqual(terrain._search_workspace.generation, 1)
        self.assertEqual(find_path(terrain, (15, 15), (0, 0)), reference_search(terrain, (15, 15), (0, 0)))

    def test_remote_revision_still_respects_live_occupancy_rerouting(self):
        e = Engine(Config(size=32, food_count=0, combat_enabled=False, reproduction_enabled=False))
        a = e.world.ants[0]
        a.position = (10, 10)
        a.route, a.route_goal = [(11, 10), (12, 10)], (12, 10)
        a.route_revision = e.world.terrain.revision
        e.world.terrain.occupancy[10, 11] = 1
        e.world.terrain.dig(25, 25)
        # Static routes survive remote excavation; live occupancy is handled locally.
        self.assertEqual(route_step(e.world, a, a.position, a.route_goal),(11,10))
        self.assertEqual(a.route,[(11,10),(12,10)])
        chosen=e.fsm._traffic(a,a.position,a.route[0])
        self.assertLessEqual(abs(chosen[0]-10)+abs(chosen[1]-10),1)
        self.assertTrue(chosen==a.position or e.world.terrain.available(*chosen))

class BenchmarkRegressionTests(unittest.TestCase):
    def test_comparison_rejects_behavior_or_population_changes(self):
        header = dict(map_size=512, seed=7, turns_requested=1, profiled=False, python='test', numpy='test')
        record = dict(scenario='contact', initial_ants=100, final_ants=90, turns=1, attacks=10,
                      births=0, ant_deaths=10, queenless=0, ended=False, fingerprints=['initial', 'turn1'],
                      populations=[90], mean_ms_per_turn=10, max_ms_per_turn=10)
        before = [header, record]
        after = copy.deepcopy(before)
        after[1]['mean_ms_per_turn'] = after[1]['max_ms_per_turn'] = 5
        self.assertEqual(compare(before, after)['results'][0]['mean_speedup'], 2)
        after[1]['fingerprints'][1] = 'changed'
        with self.assertRaises(AssertionError):
            compare(before, after)
        after[1]['fingerprints'] = list(record['fingerprints'])
        after[1]['populations'] = [80]
        with self.assertRaises(AssertionError):
            compare(before, after)

class ScentCacheRegressionTests(unittest.TestCase):
    def make(self):
        # This regression tracks exactly one source's cached BFS footprint.
        e = Engine(Config(size=32, supply_stations_enabled=False, food_count=0, stone_density=0, large_stone_density=0))
        e.world.food = [Food(100, (15, 15), 'medium', 10, 8, age=8)]
        e.food.rebuild_scent()
        return e

    def test_dig_and_remote_topology_changes_reuse_identical_field(self):
        e = self.make()
        footprint = next(iter(e.food.footprints.values()))
        scent = dict(e.food.scent)
        e.world.terrain.dig(16, 15)
        e.food.rebuild_scent()
        self.assertIs(next(iter(e.food.footprints.values())), footprint)
        e.world.terrain.set(31, 31, STONE)
        e.food.rebuild_scent()
        self.assertIs(next(iter(e.food.footprints.values())), footprint)
        self.assertEqual(e.food.scent, scent)

    def test_local_obstruction_and_opening_refresh_exact_bfs(self):
        e = self.make()
        original = dict(e.food.scent)
        footprint = next(iter(e.food.footprints.values()))
        e.world.terrain.set(16, 15, STONE)
        e.food.rebuild_scent()
        self.assertEqual(e.food.sample((16, 15)), 0)
        self.assertIsNot(next(iter(e.food.footprints.values())), footprint)
        # A forced full rebuild must produce exactly the same world field.
        cached = dict(e.food.scent)
        e.food.footprints.clear()
        e.food.rebuild_scent()
        self.assertEqual(e.food.scent, cached)
        e.world.terrain.set(16, 15, SOIL)
        e.food.rebuild_scent()
        self.assertEqual(e.food.scent, original)

    def test_capacity_change_keeps_global_route_revision(self):
        terrain = Terrain(16)
        revision = terrain.revision
        local = terrain.topology_version_near((5, 5), 3)
        terrain.dig(5, 5)
        self.assertGreater(terrain.revision, revision)
        self.assertEqual(terrain.topology_version_near((5, 5), 3), local)
        terrain.set(5, 5, STONE)
        self.assertGreater(terrain.topology_version_near((5, 5), 3), local)
