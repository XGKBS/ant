import unittest
import copy
import numpy as np
from config import Config, PERKS
from entities.models import Ant, Food
from simulation.engine import Engine
from simulation.terrain import SOIL, STONE, PASSAGE
from systems.perks import movement, sensing, load, cost_half, queen_sensing
from ai.pheromones import FOOD, BATTLE

def make(perk='production', reproduction=False, combat=True, **kwargs):
    # Isolate original production costs/bonuses from the new reserve allocation policy.
    kwargs.setdefault('strategic_reserves_enabled', False)
    e = Engine(Config(size=64, food_count=0, stone_density=0, large_stone_density=0,
                      perks=(perk,)*4, reproduction_enabled=reproduction, combat_enabled=combat, **kwargs))
    e.world.ants.clear()
    e.world.terrain.occupancy[:] = 0
    return e

def add(e, faction, position, kind='worker', hp=None):
    ant = Ant(e.world.allocate_id(), faction, position, kind=kind, hp=hp)
    ant.path = [position]*(movement(ant, e.world.colonies[faction])+1)
    e.world.ants.append(ant)
    e.world.terrain.occupancy[position[1], position[0]] += 1
    return ant

def kill_queen(e, faction, turn=0):
    e.world.colonies[faction].queen.hp = 0
    e.lifecycle.cleanup(turn)

def action(e, ant, turn):
    ant.action_used, ant.last_action = False, None
    e.fsm.resolve_action(ant, turn)

class EconomyTests(unittest.TestCase):
    def test_nonproduction_queen_saves_for_upgrade(self):
        e = make('exploration', reproduction=True)
        c = e.world.colonies[0]
        for i in range(8):
            add(e, 0, (10+i, 10))
        c.reserves = 8
        e.reproduction.tick(1)
        self.assertTrue(c.saving_upgrade)
        self.assertEqual(c.reserves, 8)
        self.assertEqual(len(e.world.ants), 8)
        c.reserves = 10
        e.reproduction.tick(2)
        self.assertTrue(c.upgraded)
        self.assertEqual(c.reserves, 0)
        c.threat, c.reserves = 'critical', 2
        e.reproduction.tick(3)
        self.assertEqual(e.world.ants[-1].kind, 'soldier')

    def test_integrated_deliveries_fund_births_without_creating_food(self):
        # Closed 25-food reproduction fixture: exclude the newly approved supplies.
        e = Engine(Config(size=64, strategic_reserves_enabled=False, supply_stations_enabled=False, perks=('exploration',)*4, stone_density=0, large_stone_density=0, food_count=0))
        e.world.food = [Food(e.world.allocate_id(), (7, 2), 'large', 25, 16, age=16)]
        e.food.rebuild_scent()
        # Restore committed positions before replanning the changed test environment.
        e.world.terrain.occupancy[:] = 0
        for ant in e.world.ants:
            e.world.terrain.occupancy[ant.position[1], ant.position[0]] += 1
        e._plan()
        for _ in range(20):
            e.advance(1)
            accounted = sum(f.units for f in e.world.food) + sum(a.cargo for a in e.world.ants)
            accounted += sum(c.reserves+c.spent_half/2 for c in e.world.colonies) + e.food.eaten + e.food.discarded
            self.assertEqual(accounted, 25)
        self.assertGreater(sum(c.spent_half for c in e.world.colonies), 0)

    def test_paid_upgrade_conservation_and_one_birth_limit(self):
        e = make(reproduction=True)
        c = e.world.colonies[0]
        c.reserves = 16
        e.reproduction.tick(1)
        self.assertTrue(c.upgraded)
        self.assertEqual(c.reserves, 6)
        self.assertEqual(len(e.world.ants), 0)
        for turn in range(2, 5):
            before = len(e.world.ants)
            e.reproduction.tick(turn)
            e.reproduction.tick(turn)  # Idempotent for the same queen/turn.
            self.assertEqual(len(e.world.ants), before+1)
            self.assertEqual(c.reserves_half+c.spent_half, 32)
        self.assertEqual(c.reserves, 0)
        self.assertEqual(c.upgrade_spent_half, 20)

    def test_unupgraded_queen_only_workers_under_critical_threat(self):
        e = make(reproduction=True)
        c = e.world.colonies[0]
        c.threat, c.reserves = 'critical', 8
        e.reproduction.tick(1)
        self.assertEqual(e.world.ants[0].kind, 'worker')
        self.assertFalse(c.upgraded)
        self.assertEqual(c.reserves, 6)

    def test_spawn_blocked_does_not_charge_or_consume_bonus(self):
        e = make(reproduction=True)
        c = e.world.colonies[0]
        c.upgraded, c.reserves = True, 8
        c.bonus_queue = ['worker']
        for p in e.fsm.base_cells(Ant(999, 0, (1, 1))):
            e.world.terrain.set(*p, STONE)
        e.reproduction.tick(1)
        self.assertEqual(c.reserves, 8)
        self.assertEqual(c.bonus_queue, ['worker'])
        self.assertFalse(e.world.ants)

    def test_fractional_worker_cost(self):
        e = make('exploration', reproduction=True)
        c = e.world.colonies[0]
        c.reserves = 4.5
        for turn in range(1, 4):
            e.reproduction.tick(turn)
        self.assertEqual(len(e.world.ants), 3)
        self.assertEqual(c.reserves_half, 0)
        self.assertEqual(c.spent_half, 9)

    def test_fractional_soldier_cost_and_no_transport(self):
        e = make('warfare', reproduction=True)
        c = e.world.colonies[0]
        c.reserves, c.upgraded, c.threat = 3, True, 'critical'
        e.reproduction.tick(1)
        soldier = e.world.ants[0]
        self.assertEqual((soldier.kind, soldier.hp, soldier.damage), ('soldier', 12, 3))
        e.world.food = [Food(e.world.allocate_id(), soldier.position, 'small', 5, 4)]
        action(e, soldier, 1)
        self.assertEqual(soldier.cargo, 1)
        self.assertEqual(e.world.food[0].units, 4)
        e.reproduction.tick(2)
        self.assertEqual(c.reserves, 0)
        self.assertEqual(c.spent_half, 6)

    def test_production_free_upgrade_and_deferred_bonus(self):
        e = make(reproduction=True)
        c = e.world.colonies[0]
        for turn in range(1, 11):
            c.reserves += 2
            e.reproduction.tick(turn)
            # Free space without killing or introducing food; isolate queen accounting.
            e.world.ants.clear()
            e.world.terrain.occupancy[:] = 0
        self.assertTrue(c.upgraded)
        self.assertEqual(c.upgrade_spent_half, 0)
        self.assertEqual(c.produced_workers, 10)
        for turn in range(11, 21):
            c.reserves += 2
            e.reproduction.tick(turn)
            e.world.ants.clear()
            e.world.terrain.occupancy[:] = 0
        self.assertEqual(c.bonus_queue, ['worker'])
        self.assertEqual(c.bonus_births, 0)
        e.reproduction.tick(21)
        self.assertEqual(len(e.world.ants), 1)
        self.assertEqual(c.bonus_births, 1)
        self.assertEqual(c.spent_half, 80)
        self.assertEqual(c.reserves, 0)

    def test_production_bonus_soldier_uses_a_later_turn(self):
        e = make(reproduction=True)
        c = e.world.colonies[0]
        c.upgraded, c.threat = True, 'critical'
        for turn in range(1, 11):
            c.reserves += 2
            e.reproduction.tick(turn)
            e.world.ants.clear()
            e.world.terrain.occupancy[:] = 0
        self.assertEqual(c.bonus_queue, ['soldier'])
        e.reproduction.tick(11)
        self.assertEqual([a.kind for a in e.world.ants], ['soldier'])
        self.assertEqual(c.spent_half, 40)

    def test_bonus_birth_counts_toward_next_same_type_milestone(self):
        e = make(reproduction=True)
        c = e.world.colonies[0]
        c.upgraded, c.threat = True, 'critical'
        for turn in range(1, 21):
            if turn != 11:
                c.reserves += 2
            e.reproduction.tick(turn)
            e.world.ants.clear()
            e.world.terrain.occupancy[:] = 0
        self.assertEqual(c.post_upgrade_counts['soldier'], 20)
        self.assertEqual(c.bonus_queue, ['soldier'])
        self.assertEqual(c.bonus_births, 1)
        self.assertEqual(c.spent_half, 76)

    def test_adaptive_production_ratios(self):
        for threat, soldiers in [('safe', 0), ('alert', 2), ('contact', 4), ('near-base', 6), ('critical', 8)]:
            e = make('speed', reproduction=True)
            c = e.world.colonies[0]
            c.upgraded, c.reserves, c.threat = True, 16, threat
            produced = []
            for turn in range(1, 9):
                e.reproduction.tick(turn)
                produced.extend(a.kind for a in e.world.ants)
                e.world.ants.clear()
                e.world.terrain.occupancy[:] = 0
            self.assertEqual(produced.count('soldier'), soldiers)
            self.assertEqual(c.reserves, 0)

class PerkTests(unittest.TestCase):
    def test_speed_blitz_actual_movement_and_reversion(self):
        for perk, kind, budget, normal in [('speed', 'worker', 3, 2), ('blitz', 'soldier', 4, 3)]:
            # Isolate the movement perk from intentional shared-route warm-up waits.
            e = make(perk, combat=False, supply_stations_enabled=False)
            a = add(e, 0, (15, 15), kind)
            a.heading = (1, 0)
            e._plan()
            self.assertEqual(a.planned_budget, budget)
            self.assertEqual(len(a.path)-1, budget)
            self.assertEqual(sum(p != q for p, q in zip(a.path, a.path[1:])), budget)
            # Restore committed occupancy before an external fixture event.
            e.world.terrain.occupancy[:] = 0
            e.world.terrain.occupancy[15, 15] = 1
            kill_queen(e, 0)
            self.assertEqual(movement(a, e.world.colonies[0]), normal)
            e._plan()
            self.assertEqual(a.planned_budget, normal)

    def test_heavy_lifting_actual_fractional_pickup_and_loss(self):
        e = make('heavy-lifting')
        a = add(e, 0, (15, 15))
        f = Food(e.world.allocate_id(), a.position, 'small', 5, 4)
        e.world.food = [f]
        action(e, a, 1)
        self.assertEqual((a.cargo, f.units), (1.5, 3.5))
        kill_queen(e, 0, 1)
        self.assertEqual(load(a, e.world.colonies[0]), 1)
        self.assertEqual(a.cargo, 1)
        self.assertEqual(e.food.discarded, 0.5)
        self.assertEqual(f.units+a.cargo+e.food.discarded, 5)

    def test_sensitivity_food_and_queen_alarm_ranges(self):
        e = make('sensitivity')
        a = add(e, 0, (15, 15))
        f = Food(e.world.allocate_id(), (18, 15), 'micro', 1, 2)
        e.world.food = [f]
        e.fsm.observe(a)
        self.assertIn(f.id, a.known_food)
        self.assertEqual(sensing(a, e.world.colonies[0]), 3)
        e.pheromones.reinforce(1, FOOD, (15, 18), 4)
        e.fsm.observe(a)
        self.assertTrue(a.foreign_signal)
        e.world.colonies[0].perk = 'production'
        e.fsm.observe(a)
        self.assertFalse(a.foreign_signal)
        e.world.colonies[0].perk = 'sensitivity'
        enemy = add(e, 1, (16, 2))  # 13 cells from red queen's nearest footprint.
        e.combat.refresh()
        e.strategy.assess(0)
        self.assertEqual(e.world.colonies[0].threat, 'contact')
        e.world.colonies[0].perk = 'production'
        e.strategy.assess(0)
        self.assertEqual(e.world.colonies[0].threat, 'safe')

    def test_greed_five_distinct_sources_next_respawn_and_loss(self):
        e = make('greed')
        c = e.world.colonies[0]
        a = add(e, 0, (15, 15))
        sources = [Food(e.world.allocate_id(), (5+10*i, 20), 'small', 5, 4) for i in range(5)]
        e.world.food = sources
        for _ in range(3):
            e.food.harvest(sources[0], 1, ant=a)
        self.assertFalse(c.greed_credits)

        for f in sources[1:]:
            e.food.harvest(f, 1, ant=a)
        self.assertEqual(c.greed_credits['small'], 1)
        for f in sources[:2]:
            f.units, f.respawn_deadline = 0, 26
        e.food.tick(26)
        self.assertEqual(sources[0].tier, 'small')
        self.assertEqual(sources[1].tier, 'micro')
        self.assertEqual(c.greed_credits['small'], 0)
        c.greed_credits['small'] = 1
        kill_queen(e, 0, 26)
        self.assertFalse(c.greed_credits)

    def test_greed_does_not_override_explicit_micro_retirement(self):
        e = make('greed', micro_respawn_tier=None)
        c = e.world.colonies[0]
        c.greed_credits['micro'] = 1
        f = Food(e.world.allocate_id(), (20, 20), 'micro', 0, 2, respawn_deadline=25)
        e.world.food = [f]
        e.food.tick(25)
        self.assertEqual(f.units, 0)
        self.assertIsNone(f.respawn_deadline)
        self.assertEqual(c.greed_credits['micro'], 1)

    def test_all_perks_stop_on_queen_death(self):
        for perk in PERKS:
            e = make(perk)
            c = e.world.colonies[0]
            worker = add(e, 0, (15, 15))
            soldier = add(e, 0, (16, 15), 'soldier')
            kill_queen(e, 0)
            self.assertIsNone(c.active_perk)
            self.assertEqual(movement(worker, c), 2)
            self.assertEqual(movement(soldier, c), 3)
            self.assertEqual(load(worker, c), 1)
            self.assertEqual(sensing(worker, c), 2)
            self.assertEqual(queen_sensing(c, e.config), 10)
            self.assertEqual(cost_half('worker', c), 4)
            self.assertEqual(cost_half('soldier', c), 4)

class CombatAndSurvivalTests(unittest.TestCase):
    def test_mutual_lethal_attacks_land_and_no_loot(self):
        e = make()
        a = add(e, 0, (15, 15), 'soldier', hp=3)
        b = add(e, 1, (16, 15), 'soldier', hp=3)
        e.combat.resolve(1)
        self.assertEqual((a.hp, b.hp), (0, 0))
        e.lifecycle.cleanup(1)
        self.assertFalse(e.world.ants)
        self.assertFalse(e.world.food)

    def test_simultaneous_soldier_worker_combat_and_no_extra_action(self):
        e = make()
        soldier = add(e, 0, (15, 15), 'soldier')
        worker = add(e, 1, (16, 15))
        e.world.food = [Food(e.world.allocate_id(), soldier.position, 'small', 5, 4)]
        e.combat.resolve(1)
        self.assertEqual((soldier.hp, worker.hp), (11, 2))
        self.assertTrue(soldier.action_used)
        e.fsm.resolve_action(soldier, 1)
        self.assertEqual(e.world.food[0].units, 5)
        self.assertEqual(soldier.last_action, 'attack')
        e.combat.resolve(1)
        self.assertEqual((soldier.hp, worker.hp), (11, 2))

    def test_queen_cannot_attack_and_trophy_once(self):
        e = make()
        queen = e.world.colonies[0].queen
        a = add(e, 1, (1, 2), 'soldier')
        queen.hp = 3
        e.combat.resolve(1)
        self.assertEqual(queen.hp, 0)
        self.assertEqual(a.hp, 12)
        self.assertEqual(queen.damage, 0)
        e.lifecycle.cleanup(1)
        self.assertFalse(e.world.colonies[0].alive)
        self.assertEqual(sum(f.units for f in e.world.food), e.config.trophy_units)
        self.assertEqual(e.world.food[0].tier, 'trophy')
        e.lifecycle.cleanup(2)
        self.assertEqual(len(e.world.food), 1)
        for x, y in queen.footprint:
            self.assertEqual(e.world.terrain.capacity[y, x], 1)

    def test_ant_death_releases_occupancy_without_loot(self):
        e = make()
        a = add(e, 0, (15, 15), hp=1)
        b = add(e, 1, (16, 15), 'soldier')
        e.combat.resolve(1)
        e.lifecycle.cleanup(1)
        self.assertNotIn(a, e.world.ants)
        self.assertIn(b, e.world.ants)
        self.assertEqual(e.world.terrain.occupancy[15, 15], 0)
        self.assertFalse(e.world.food)

    def test_queenless_hunger_death_relative_five_turns(self):
        e = make()
        a = add(e, 0, (15, 15))
        kill_queen(e, 0, 3)
        for turn in range(4, 8):
            e.lifecycle.hunger(turn)
        self.assertEqual(a.hp, 5)
        e.lifecycle.hunger(8)
        self.assertEqual(a.hp, 4)
        e.lifecycle.hunger(13)
        self.assertEqual(a.hp, 3)

    def test_queenless_soldier_eats_without_transport_and_healing_caps(self):
        e = make()
        a = add(e, 0, (15, 15), 'soldier', hp=11.5)
        f = Food(e.world.allocate_id(), a.position, 'small', 5, 4)
        e.world.food = [f]
        kill_queen(e, 0)
        action(e, a, 1)
        self.assertEqual(a.hp, 12)
        self.assertEqual(f.units, 4.5)
        self.assertEqual(a.cargo, 0)
        self.assertEqual(a.last_action, 'eat')
        action(e, a, 2)
        self.assertEqual(f.units, 4.5)
        self.assertEqual(e.world.colonies[0].reserves, 0)

    def test_dead_ant_cannot_eat_or_revive(self):
        e = make()
        a = add(e, 0, (15, 15), hp=0)
        f = Food(e.world.allocate_id(), a.position, 'large', 25, 16)
        e.world.food = [f]
        kill_queen(e, 0)
        action(e, a, 1)
        self.assertEqual(a.hp, 0)
        self.assertEqual(f.units, 25)
        self.assertNotIn(a, e.world.ants)

    def test_queenless_worker_eats_carried_food(self):
        e = make()
        a = add(e, 0, (15, 15), hp=3)
        a.cargo = 1
        kill_queen(e, 0)
        action(e, a, 1)
        self.assertEqual((a.hp, a.cargo), (4, 0))

    def test_queenless_aggression_and_defense_fsm(self):
        e = make()
        a = add(e, 0, (15, 15))
        b = add(e, 1, (17, 15))
        kill_queen(e, 0)
        e.combat.refresh()
        e.fsm.prepare(a)
        self.assertEqual(a.state, 'fight')
        self.assertEqual(a.combat_target, ('ant', b.id))
        self.assertEqual(a.target, (16, 15))

    def test_queenless_no_birth_upgrade_or_resurrection(self):
        e = make(reproduction=True)
        c = e.world.colonies[0]
        c.reserves, c.produced_workers = 30, 10
        kill_queen(e, 0)
        c.queen.hp = 50  # A historical death permanently removes eligibility.
        e.reproduction.tick(1)
        self.assertFalse(c.alive)
        self.assertEqual(c.reserves, 30)
        self.assertFalse(c.upgraded)
        self.assertFalse(e.world.ants)

    def test_trophy_merges_without_violating_spacing_and_never_respawns(self):
        e = make()
        f = Food(e.world.allocate_id(), (1, 2), 'small', 5, 4)
        e.world.food = [f]
        kill_queen(e, 0)
        self.assertEqual(len(e.world.food), 1)
        self.assertEqual((f.tier, f.units), ('trophy', 55))
        e.food.harvest(f, 1, 55)
        self.assertIsNone(f.respawn_deadline)
        e.food.tick(26)
        self.assertEqual(f.units, 0)

class ThreatAndIntegrationTests(unittest.TestCase):
    def test_manual_end_preserves_final_entities_food_and_expenses(self):
        e = make(reproduction=True)
        e.world.colonies[0].reserves = 16
        e.advance(3)
        e.end()
        colonies, ants, food = copy.deepcopy((e.world.colonies, e.world.ants, e.world.food))
        occupancy = e.world.terrain.occupancy.copy()
        e.advance(100)
        self.assertEqual(e.turn, 3)
        self.assertEqual(e.world.colonies, colonies)
        self.assertEqual(e.world.ants, ants)
        self.assertEqual(e.world.food, food)
        np.testing.assert_array_equal(e.world.terrain.occupancy, occupancy)

    def test_soldiers_follow_battle_trails_without_food_transport(self):
        e = make()
        a = add(e, 0, (15, 15), 'soldier')
        e.pheromones.reinforce(0, BATTLE, (16, 15), 10)
        e._plan()
        self.assertEqual(a.state, 'investigate')
        self.assertEqual(a.path[1], (16, 15))
        self.assertEqual(a.cargo, 0)

    def test_ui_catchup_budget_preserves_every_pending_tick(self):
        a, b = make(), make()
        a.advance(3.5)
        b.advance(3.5, max_ticks=1)
        self.assertEqual((b.turn, b.progress), (1, 2.5))
        b.paused = True
        b.advance(0, max_ticks=1)
        self.assertEqual(b.turn, 1)
        b.paused = False
        b.advance(0, max_ticks=1)
        b.advance(0, max_ticks=1)
        self.assertEqual((b.turn, b.progress), (a.turn, a.progress))
        self.assertEqual(a.world.colonies, b.world.colonies)

    def test_worker_reports_foreign_information_to_queen(self):
        e = make()
        a = add(e, 0, (15, 15))
        e.pheromones.reinforce(1, FOOD, a.position, 4)
        e.fsm.prepare(a)
        self.assertEqual(a.state, 'return-report')
        self.assertEqual(a.pending_report, (15, 15))
        # Test arrival and report action separately from the pathfinding fixture.
        e.world.terrain.occupancy[15, 15] = 0
        a.position = (1, 2)
        e.world.terrain.occupancy[2, 1] = 1
        action(e, a, 10)
        self.assertEqual(a.last_action, 'report')
        self.assertEqual(e.world.colonies[0].report_position, (15, 15))
        e.strategy.assess(10)
        self.assertEqual(e.world.colonies[0].threat, 'alert')

    def test_threat_levels_foreign_signals_enemies_and_attacks(self):
        e = make()
        c = e.world.colonies[0]
        e.combat.refresh()
        e.strategy.assess(1)
        self.assertEqual(c.threat, 'safe')
        e.pheromones.reinforce(1, FOOD, (6, 2), 4)
        e.strategy.assess(1)
        self.assertEqual(c.threat, 'alert')
        enemy = add(e, 1, (12, 2))
        e.combat.refresh()
        e.strategy.assess(1)
        self.assertEqual(c.threat, 'contact')
        enemy.position = (7, 2)
        e.combat.refresh()
        e.strategy.assess(1)
        self.assertEqual(c.threat, 'near-base')
        c.queen.last_attacked_turn = 1
        e.strategy.assess(1)
        self.assertEqual(c.threat, 'critical')
        defender = add(e, 0, (20, 20))
        e.fsm.prepare(defender)
        self.assertEqual(defender.state, 'defend')

    def test_last_queen_wins_and_cap_no_winner(self):
        e = make()
        for faction in (0, 1, 2):
            kill_queen(e, faction)
        e.advance(1)
        self.assertTrue(e.ended)
        self.assertEqual(e.winner, 3)
        self.assertIn('Green wins', e.outcome)
        result = e.outcome
        e.end()
        self.assertEqual(e.outcome, result)
        e = make(max_turns=1)
        e.advance(1)
        self.assertTrue(e.ended)
        self.assertIsNone(e.winner)
        self.assertIn('no winner', e.outcome)

    def test_all_queens_simultaneous_death_no_winner(self):
        e = make()
        for c in e.world.colonies:
            c.queen.hp = 1
            x, y = c.queen.position
            add(e, (c.faction+1) % 4, (x-1, y), 'soldier')
        e.advance(1)
        self.assertTrue(e.ended)
        self.assertIsNone(e.winner)
        self.assertEqual(sum(c.alive for c in e.world.colonies), 0)
        self.assertEqual(sum(f.tier == 'trophy' for f in e.world.food), 4)

    def test_deterministic_integrated_economy_combat_and_capacity(self):
        a = Engine(Config(size=64, perks=('heavy-lifting', 'sensitivity', 'greed', 'blitz')))
        b = Engine(Config(size=64, perks=('heavy-lifting', 'sensitivity', 'greed', 'blitz')))
        for _ in range(150):
            for e in (a, b):
                e.advance(1)
                t = e.world.terrain
                counts = np.zeros_like(t.occupancy)
                for ant in e.world.ants:
                    counts[ant.path[-1][1], ant.path[-1][0]] += 1
                    self.assertLessEqual(len(ant.path)-1, movement(ant, e.world.colonies[ant.faction]))
                np.testing.assert_array_equal(counts, t.occupancy)
                self.assertTrue(np.all(t.occupancy <= t.capacity))
        self.assertEqual(a.world.ants, b.world.ants)
        self.assertEqual(a.world.colonies, b.world.colonies)
        self.assertEqual(a.world.food, b.world.food)
        np.testing.assert_array_equal(a.pheromones.values, b.pheromones.values)
        ids = [ant.id for ant in a.world.ants] + [f.id for f in a.world.food] + [c.queen.id for c in a.world.colonies]
        self.assertEqual(len(ids), len(set(ids)))
