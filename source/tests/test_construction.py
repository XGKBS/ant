import unittest
from fractions import Fraction
import numpy as np
from config import Config
from entities.models import Ant, Food
from simulation.engine import Engine
from simulation.terrain import SOIL, PASSAGE, STONE, LARGE_STONE, REINFORCED
from systems.stones import speed_ratio


def fixture(perk='production', **overrides):
    # Bespoke stone/soil geometry; no unrelated fixed food sites in this fixture.
    e = Engine(Config(size=32, supply_stations_enabled=False, food_count=0, stone_density=0, large_stone_density=0,
                      combat_enabled=False, reproduction_enabled=False, perks=(perk,)*4, **overrides))
    e.world.ants.clear()
    e.world.terrain.occupancy[:] = 0
    return e


def put(e, p, kind='worker', faction=0):
    a = Ant(e.world.allocate_id(), faction, p, kind=kind)
    a.path = [p]
    e.world.ants.append(a)
    e.world.terrain.occupancy[p[1], p[0]] += 1
    return a


def soil(e, p, units):
    """Real excavation, not creation of test-only free material."""
    t = e.world.terrain
    for y in range(15, 31):
        for x in range(15, 31):
            if units and t.dig(x, y):
                t.withdraw((x, y))
                t.deposit(p, 1)
                units -= 1
    assert units == 0


def arm(e, job, ants):
    job.crew = [a.id for a in ants]
    for a in ants:
        a.construction_task, a.state = job.id, 'move-stone' if job.kind == 'stone' else 'compose-stone'
        a.action_used, a.last_action = False, None


class SoilTests(unittest.TestCase):
    def test_dig_transfer_fill_strength_conservation(self):
        e = fixture()
        c, t = e.construction, e.world.terrain
        a = put(e, (10, 10))
        before = c.soil_total()
        self.assertTrue(c.dig(a, (11, 10), 1))
        self.assertEqual((a.soil_cargo, t.capacity[10, 11]), (1, 4))
        self.assertEqual(c.soil_total(), before)
        a.state, a.target, a.action_used = 'fill', (11, 10), False
        self.assertTrue(c.action(a, 2))
        self.assertEqual((t.layers[10, 11], t.strength((11, 10)), t.capacity[10, 11]), (1, 1, 1))
        self.assertFalse(t.dig(11, 10))
        for expected in (4, 9):
            soil(e, (11, 10), 1)
            self.assertTrue(t.fill((11, 10)))
            self.assertEqual(t.strength((11, 10)), expected)
            self.assertFalse(t.dig(11, 10))
            self.assertEqual(c.soil_total(), before)
        soil(e, (11, 10), 1)
        self.assertFalse(t.fill((11, 10)))
        self.assertEqual(c.soil_total(), before)

    def test_no_free_fill_and_reject_out_of_bounds(self):
        e = fixture()
        t = e.world.terrain
        self.assertFalse(t.fill((9, 9)))
        self.assertFalse(t.fill((-1, 9)))
        self.assertFalse(t.dig(32, 0))
        self.assertEqual(t.layers[9, 9], 1)
        soil(e, (9, 9), 2)
        self.assertFalse(t.withdraw((9, 9), 0.5))
        self.assertEqual(t.loose_soil[(9, 9)], 2)

    def test_loaded_digger_leaves_ground_material(self):
        e = fixture()
        a = put(e, (10, 10), 'soldier')
        a.cargo = 1  # synthetic load; excavation still obeys carrying capacity
        self.assertTrue(e.construction.dig(a, (11, 10), 1))
        self.assertEqual(a.soil_cargo, 0)
        self.assertEqual(e.world.terrain.loose_soil[(11, 10)], 1)

    def test_fill_capacity_rejection_is_atomic(self):
        e = fixture()
        t = e.world.terrain
        t.dig(10, 10)
        put(e, (10, 10))
        put(e, (10, 10))
        before = e.construction.soil_total()
        self.assertFalse(t.fill((10, 10)))
        self.assertEqual((t.capacity[10, 10], t.loose_soil[(10, 10)]), (4, 1))
        self.assertEqual(e.construction.soil_total(), before)

    def test_one_action_prevents_double_dig_fill_collect(self):
        e = fixture()
        a = put(e, (10, 10))
        c = e.construction
        self.assertTrue(c.dig(a, (11, 10), 1))
        self.assertFalse(c.dig(a, (10, 11), 1))
        a.state, a.target = 'fill', (11, 10)
        self.assertFalse(c.action(a, 1))
        self.assertEqual(e.world.terrain.cells[10, 11], PASSAGE)

    def test_death_drops_material_and_queen_loss_unloads_soil(self):
        e = fixture('heavy-lifting')
        a = put(e, (10, 10))
        self.assertTrue(e.construction.dig(a, (11, 10), 1))
        before = e.construction.soil_total()
        a.cargo = 0.5
        e.world.colonies[0].queen.hp = 0
        e.lifecycle.cleanup(2)
        self.assertEqual((a.soil_cargo, a.cargo), (0, 0.5))
        self.assertEqual(e.construction.soil_total(), before)
        a.soil_cargo = 1
        e.world.terrain.withdraw(a.position)
        a.hp = 0
        e.lifecycle.cleanup(3)
        self.assertEqual(e.construction.soil_total(), before)
        self.assertEqual(e.world.terrain.occupancy[10, 10], 0)
        self.assertEqual(len(e.world.food), 1)  # queen trophy only, never ant loot

    def test_reinforced_traversal_and_action_access(self):
        e = fixture()
        soil(e, (11, 10), 1)
        self.assertTrue(e.world.terrain.fill((11, 10)))
        a = put(e, (10, 10), 'soldier')
        self.assertIn((11, 10), __import__('ai.pathfinding', fromlist=['neighbors']).neighbors(e.world.terrain, a.position))
        self.assertFalse(e.construction.dig(a, (11, 10), 1))
        a.position = (5, 5)
        self.assertFalse(e.construction.dig(a, (10, 10), 1))


class StoneTests(unittest.TestCase):
    def test_configurable_composition_adjacency_and_access(self):
        e = fixture(composition_min_shared_edges=2)
        s = e.construction.stones
        a = s.register([(10, 10)], 4)
        b = s.register([(11, 10)], 4)
        self.assertFalse(s.can_compose((a.id, b.id)))
        a = s.register([(20, 10), (20, 11)], 8)
        b = s.register([(21, 10), (21, 11)], 8)
        self.assertTrue(s.can_compose((a.id, b.id)))
        e = fixture(composition_access_radius=1)
        a = e.construction.stones.register([(10, 10)], 4)
        b = e.construction.stones.register([(11, 10)], 4)
        self.assertIsNone(e.construction.create(0, 'compose', (10, 9), (a.id, b.id)))

    def test_configurable_initial_weights_and_slow_work_rate(self):
        e = Engine(Config(size=32, food_count=0, stone_density=.1, large_stone_density=.01,
                          ordinary_stone_weight=6, large_stone_weight_per_cell=5, stone_base_speed=.5))
        groups = list(e.construction.stones.groups.values())
        self.assertTrue(any(s.kind == STONE for s in groups))
        self.assertTrue(any(s.kind == LARGE_STONE for s in groups))
        for s in groups:
            self.assertEqual(s.weight, 6 if s.kind == STONE else len(s.cells)*5)
        e = fixture(stone_base_speed=.5)
        c = e.construction
        s = c.stones.register([(10, 10)], 4)
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        ants = [put(e, p) for p in c.work_cells(job)[:4]]
        for turn in (1, 2):
            arm(e, job, ants)
            c.resolve(turn)
            self.assertEqual(s.cells, ((10, 10),) if turn == 1 else ((11, 10),))

    def test_stones_and_worksites_are_exclusively_claimed(self):
        e = fixture()
        c = e.construction
        a = c.stones.register([(10, 10)], 4)
        b = c.stones.register([(11, 10)], 4)
        job = c.create(0, 'compose', (10, 9), (a.id, b.id))
        self.assertIsNotNone(job)
        self.assertIsNone(c.create(1, 'stone', (10, 10), (a.id,), (-1, 0)))
        self.assertIsNone(c.create(1, 'compose', (10, 9), (a.id, b.id)))
        c.finish(job)
        self.assertIsNotNone(c.create(1, 'stone', (10, 10), (a.id,), (-1, 0)))

    def test_eight_ordinary_ants_move_weight_eight_in_one_turn(self):
        e = fixture()
        c = e.construction
        s = c.stones.register([(10, 10), (10, 11)], 8, LARGE_STONE)
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        ants = [put(e, p) for p in c.work_cells(job)[:8]]
        arm(e, job, ants)
        c.resolve(1)
        self.assertEqual(s.cells, ((11, 10), (11, 11)))
        self.assertTrue(all(a.last_action == 'move-stone' for a in ants))

    def test_large_stone_actual_teamwork_and_dead_helper_exclusion(self):
        e = fixture()
        c = e.construction
        s = c.stones.register([(10, 10), (11, 10), (10, 11), (11, 11)], 16, LARGE_STONE)
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        ants = [put(e, p) for p in c.work_cells(job)[:8]]
        arm(e, job, ants)
        ants[-1].hp = 0
        c.resolve(1)
        self.assertEqual(job.progress, 0)
        # Death removes occupancy; a genuinely new ant may replace that helper.
        e.lifecycle.cleanup(1)
        ants[-1] = put(e, ants[-1].position)
        for turn in range(2, 6):
            arm(e, job, ants)
            c.resolve(turn)
        self.assertEqual(s.cells, ((11, 10), (11, 11), (12, 10), (12, 11)))

    def test_foreign_helper_cannot_contribute(self):
        e = fixture()
        c = e.construction
        s = c.stones.register([(10, 10)], 4)
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        ants = [put(e, (9, 10)), put(e, (10, 9), faction=1)]
        arm(e, job, ants)
        c.resolve(1)
        self.assertEqual(job.progress, 0)

    def test_speed_reference_points_and_interpolation(self):
        cfg = Config(size=32)
        self.assertEqual(speed_ratio(3, 8, cfg), 0)
        self.assertEqual(speed_ratio(4, 8, cfg), Fraction(1, 4))
        self.assertEqual(speed_ratio(6, 8, cfg), Fraction(5, 8))
        self.assertEqual(speed_ratio(8, 8, cfg), 1)
        self.assertEqual(speed_ratio(12, 8, cfg), 1)

    def test_quarter_speed_requires_four_work_turns(self):
        e = fixture()
        c = e.construction
        s = c.stones.register([(10, 10), (10, 11)], 8, LARGE_STONE)
        ants = [put(e, p) for p in [(9, 10), (9, 11), (10, 9), (10, 12)]]
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        for turn in range(1, 5):
            arm(e, job, ants)
            c.resolve(turn)
            self.assertEqual(s.cells[0], (10, 10) if turn < 4 else (11, 10))
            self.assertTrue(all(a.action_used for a in ants))
            c.resolve(turn)  # no second action or second progress credit
        self.assertEqual(c.completed['stone'], 1)

    def test_insufficient_capacity_and_attacking_helper(self):
        e = fixture()
        c = e.construction
        s = c.stones.register([(10, 10)], 8)
        ants = [put(e, p) for p in [(9, 10), (10, 9), (10, 11)]]
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        arm(e, job, ants)
        c.resolve(1)
        self.assertEqual(job.progress, 0)
        self.assertFalse(any(a.action_used for a in ants))
        fourth = put(e, (8, 10))
        arm(e, job, ants+[fourth])
        fourth.action_used = True
        c.resolve(2)
        self.assertEqual(job.progress, 0)

    def test_heavy_lifting_immediately_lost(self):
        e = fixture('heavy-lifting')
        c = e.construction
        s = c.stones.register([(10, 10)], 8)
        ants = [put(e, p) for p in [(9, 10), (10, 9), (10, 11)]]
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        arm(e, job, ants)
        c.resolve(1)
        self.assertEqual(job.progress, Fraction(11, 32))
        e.world.colonies[0].queen.hp = 0
        e.lifecycle.cleanup(2)
        arm(e, job, ants)
        c.resolve(2)
        self.assertEqual(job.progress, Fraction(11, 32))
        self.assertEqual(s.cells, ((10, 10),))

    def test_large_atomic_relocation_preserves_substrate(self):
        e = fixture()
        c, t = e.construction, e.world.terrain
        s = c.stones.register([(10, 10), (11, 10), (10, 11), (11, 11)], 16, LARGE_STONE)
        t.dig(12, 10)
        t.withdraw((12, 10))
        t.deposit((20, 10), 1)
        before = c.soil_total()
        self.assertTrue(c.stones.move(s, (1, 0)))
        self.assertEqual(s.cells, ((11, 10), (11, 11), (12, 10), (12, 11)))
        self.assertEqual(t.capacity[10, 10], 1)
        self.assertTrue(c.stones.move(s, (1, 0)))
        self.assertTrue(c.stones.move(s, (1, 0)))
        self.assertEqual(t.capacity[10, 12], 4)
        self.assertEqual(c.soil_total(), before)
        self.assertEqual(len(c.stones.groups), 1)

    def test_invalid_destination_nothing_changes(self):
        for invalid in ('ant', 'stone', 'nest', 'food', 'pile', 'reinforced', 'bounds'):
            with self.subTest(invalid=invalid):
                e = fixture()
                c, t = e.construction, e.world.terrain
                s = c.stones.register([(0, 10)] if invalid == 'bounds' else [(10, 10)], 4)
                direction = (-1, 0) if invalid == 'bounds' else (1, 0)
                if invalid == 'ant': put(e, (11, 10))
                if invalid == 'stone': c.stones.register([(11, 10)], 4)
                if invalid == 'nest': t.set(11, 10, 4)
                if invalid == 'food': e.world.food.append(Food(99, (11, 10), 'micro', 0, 2))
                if invalid == 'pile': soil(e, (11, 10), 1)
                if invalid == 'reinforced':
                    soil(e, (11, 10), 1)
                    t.fill((11, 10))
                snapshots = [a.copy() for a in (t.cells, t.capacity, t.occupancy, t.stone_ids)]
                revision, cells = t.revision, s.cells
                self.assertFalse(c.stones.move(s, direction))
                self.assertEqual((t.revision, s.cells), (revision, cells))
                for old, new in zip(snapshots, (t.cells, t.capacity, t.occupancy, t.stone_ids)):
                    np.testing.assert_array_equal(old, new)

    def test_crew_in_destination_cannot_be_overwritten(self):
        e = fixture()
        c = e.construction
        s = c.stones.register([(10, 10)], 4)
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        ants = [put(e, (11, 10)), put(e, (10, 9))]
        arm(e, job, ants)
        c.resolve(1)
        self.assertEqual((job.progress, s.cells), (0, ((10, 10),)))

    def test_composition_five_units_conserved(self):
        e = fixture()
        c, t = e.construction, e.world.terrain
        a = c.stones.register([(10, 10)], 4)
        b = c.stones.register([(11, 10)], 4)
        worker = put(e, (10, 9), 'soldier')
        soil(e, worker.position, 5)
        before = c.soil_total()
        job = c.create(0, 'compose', worker.position, (a.id, b.id))
        for turn in range(1, 6):
            t.withdraw(worker.position)
            worker.soil_cargo += 1
            arm(e, job, [worker])
            c.resolve(turn)
            self.assertEqual(c.soil_total(), before)
            self.assertEqual(len(c.stones.groups), 2 if turn < 5 else 1)
        combined = c.stones.groups[a.id]
        self.assertEqual((combined.weight, combined.bound_soil, len(combined.cells)), (8, 5, 2))
        self.assertTrue(c.stones.move(combined, (0, 1)))
        self.assertEqual(c.soil_total(), before)

    def test_bad_composition_and_refund(self):
        e = fixture()
        c, t = e.construction, e.world.terrain
        a = c.stones.register([(10, 10)], 4)
        b = c.stones.register([(12, 10)], 4)
        self.assertIsNone(c.create(0, 'compose', (11, 9), (a.id, b.id)))
        self.assertTrue(c.stones.move(b, (-1, 0)))
        job = c.create(0, 'compose', (10, 9), (a.id, b.id))
        soil(e, job.target, 3)
        t.withdraw(job.target, 3)
        job.soil = 3
        before = c.soil_total()
        c.finish(job)
        self.assertEqual(t.loose_soil[job.target], 3)
        self.assertEqual(c.soil_total(), before)
        self.assertEqual(len(c.stones.groups), 2)


class AutonomousConstructionTests(unittest.TestCase):
    def test_full_construction_state_determinism(self):
        from benchmarks.capture_phase4b import scene
        from benchmarks.phase4b import full_fingerprint
        histories = []
        for _ in range(2):
            e, _, _ = scene('large_stone')
            history = []
            for _ in range(12):
                e.advance(1)
                history.append(full_fingerprint(e))
            histories.append(history)
        self.assertEqual(*histories)

    def test_urgent_report_keeps_priority_over_soil_work(self):
        e = fixture()
        a = put(e, (6, 5))
        e.construction.dig(a, (7, 5), 0)
        a.pending_report = (12, 12)
        e.fsm.prepare(a)
        self.assertEqual(a.state, 'return-report')

    def test_timeout_refunds_staged_soil_without_holding_ants(self):
        e = fixture()
        c, t = e.construction, e.world.terrain
        a = c.stones.register([(10, 10)], 4)
        b = c.stones.register([(11, 10)], 4)
        soil(e, (10, 9), 3)
        job = c.create(0, 'compose', (10, 9), (a.id, b.id))
        t.withdraw(job.target, 3)
        job.soil = 3
        before = c.soil_total()
        e.world.turn = e.config.construction_timeout
        c.begin_plan()
        self.assertFalse(c.tasks)
        self.assertEqual(t.loose_soil[job.target], 3)
        self.assertEqual(c.soil_total(), before)

    def test_insufficient_recruits_remain_free_to_work(self):
        e = fixture()
        c = e.construction
        s = c.stones.register([(10, 10)], 16)
        for p in [(8, 9), (8, 10), (8, 11), (9, 9)]: put(e, p, 'soldier')
        job = c.create(0, 'stone', (10, 10), (s.id,), (1, 0))
        e._plan()
        self.assertFalse(job.crew)
        self.assertTrue(all(a.construction_task is None for a in e.world.ants))

    def test_autonomous_large_stone_teamwork(self):
        from benchmarks.capture_phase4b import scene
        e, _, complete = scene('large_stone')
        before = e.construction.soil_total()
        for _ in range(30):
            e.advance(1)
            if complete(): break
        self.assertTrue(complete())
        self.assertEqual(e.construction.soil_total(), before)
        self.assertTrue(np.all(e.world.terrain.occupancy <= e.world.terrain.capacity))

    def test_exhausted_construction_demand_does_not_loop_stockpile(self):
        e = fixture()
        a = put(e, (1, 2))
        t = e.world.terrain
        soil(e, a.position, 1)
        for p in e.construction.fill_targets(a.position, a.faction):
            soil(e, p, 2)
            t.fill(p)
            t.fill(p)
        # All reachable quiet approaches are already fully reinforced.
        self.assertFalse(e.construction.fill_targets(a.position, a.faction))
        self.assertFalse(e.construction.prepare_idle(a))
        self.assertEqual(t.loose_soil[a.position], 1)

    def test_autonomous_soil_return_and_fill(self):
        e = fixture()
        a = put(e, (6, 5), 'soldier')
        self.assertTrue(e.construction.dig(a, (7, 5), 0))
        before = e.construction.soil_total()
        e._plan()
        for _ in range(8): e.advance(1)
        self.assertGreater(e.construction.completed['fill'], 0)
        self.assertEqual(e.construction.soil_total(), before)

    def test_autonomous_composition_recruitment_completion(self):
        e = fixture()
        c = e.construction
        c.stones.register([(7, 6)], 4)
        c.stones.register([(8, 6)], 4)
        positions = [(7, 5), (8, 5), (6, 5), (9, 5), (6, 6), (9, 6), (7, 4), (8, 4)]
        ants = [put(e, p, 'soldier') for p in positions]
        soil(e, (7, 5), 5)
        e.world.terrain.withdraw((7, 5))
        ants[0].soil_cargo = 1
        before = c.soil_total()
        e._plan()
        states = set()
        for _ in range(25):
            states.update(a.state for a in ants)
            e.advance(1)
            self.assertEqual(c.soil_total(), before)
            self.assertTrue(np.all(e.world.terrain.occupancy <= e.world.terrain.capacity))
            if c.completed['compose']: break
        self.assertEqual(c.completed['compose'], 1)
        self.assertIn('compose-stone', states)
        self.assertIn('collect-soil', states)

    def test_autonomous_blocked_route_recruits_and_moves_stone(self):
        e = fixture()
        c = e.construction
        # An actual impassable wall; a worker observes food across it. The normal
        # A* failure initiates relocation; no test-created construction task.
        for y in range(32): c.stones.register([(10, y)], 4)
        worker = put(e, (9, 10))
        worker.known_food[999] = (12, 10)
        e.world.food = [Food(999, (12, 10), 'small', 5, 4, age=4)]
        for p in [(8, 9), (8, 10), (8, 11), (9, 8), (9, 12), (7, 10), (7, 11)]:
            put(e, p, 'soldier')
        before = c.soil_total()
        e.food.rebuild_scent()
        e._plan()
        for _ in range(25):
            e.advance(1)
            if c.completed['stone']: break
        self.assertGreater(c.completed['stone'], 0)
        self.assertEqual(c.soil_total(), before)
        self.assertEqual(len(c.stones.groups), 32)

    def test_deterministic_integrated_conservation_and_budgets(self):
        from benchmarks.phase4a import fingerprint
        histories = []
        for _ in range(2):
            e = Engine(Config(size=32, seed=31, food_count=6, stone_density=.05))
            before = e.construction.soil_total()
            history = []
            for _ in range(35):
                e.advance(1)
                self.assertEqual(e.construction.soil_total(), before)
                t = e.world.terrain
                self.assertTrue(np.all(t.occupancy <= t.capacity))
                for a in e.world.ants:
                    self.assertLessEqual(sum(p != q for p, q in zip(a.path, a.path[1:])), a.planned_budget)
                history.append((fingerprint(e), sorted(e.construction.completed.items()),
                                [(s.cells, s.weight, s.bound_soil) for s in e.construction.stones.groups.values()]))
            histories.append(history)
        self.assertEqual(*histories)

if __name__ == '__main__':
    unittest.main()
