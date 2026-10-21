"""Strategic orders and physical storage; defaults remain enabled in these tests."""
import unittest
from dataclasses import asdict, replace
from collections import Counter
import numpy as np
from config import Config
from simulation.engine import Engine
from simulation.terrain import SOIL, STONE
from entities.models import Ant, Food
from systems.strategy import reserve_target, update_reserves


def scene(**changes):
    options = dict(size=64, food_count=0, stone_density=0, large_stone_density=0,
                   supply_stations_enabled=False, reproduction_enabled=False, combat_enabled=False)
    options.update(changes)
    e = Engine(Config(**options))
    e.world.ants.clear()
    e.world.terrain.occupancy[:] = 0
    return e


def add(e, p=(15, 15), faction=0, kind='worker'):
    a = Ant(e.world.allocate_id(), faction, p, kind=kind)
    a.path = [p]
    e.world.ants.append(a)
    e.world.terrain.occupancy[p[1], p[0]] += 1
    return a


def place(e, a, p):
    e.world.terrain.occupancy[a.position[1], a.position[0]] -= 1
    a.position = p
    a.path = [p]
    e.world.terrain.occupancy[p[1], p[0]] += 1
    a.action_used, a.last_action = False, None


def build(e, p=(25, 25), faction=0):
    c = e.world.colonies[faction]
    c.reserves = max(c.reserves, 30)
    job = e.construction.create(faction, 'depot', p)
    assert job is not None
    a = add(e, (p[0]-1, p[1]), faction)
    helper = add(e, (p[0]-1, p[1]+1), faction)
    job.crew = [a.id,helper.id]
    for ant in (a,helper):ant.construction_task = job.id
    for turn in range(1,11):
        for ant in (a,helper):ant.action_used = False
        e.construction.resolve(turn)
    assert e.world.depots
    # Fixture retains its original single-ant contract; helper has no material.
    e.world.terrain.occupancy[helper.position[1],helper.position[0]] -= 1
    e.world.ants.remove(helper)
    return e.world.depots[-1], a



class StrategyTests(unittest.TestCase):
    def test_reserve_formula_and_population_updates(self):
        c = Config()
        for n, expected in ((0,10),(2,10),(20,10),(21,11),(51,26),(1000,500)):
            self.assertEqual(reserve_target(c,n),expected)
        e=scene();a=add(e);update_reserves(e.world)
        self.assertEqual(e.world.colonies[0].reserve_target,10)
        a.hp=0;update_reserves(e.world);self.assertEqual(e.world.colonies[0].reserve_target,10)
        self.assertEqual(reserve_target(replace(c,strategic_reserve_min=3,strategic_reserve_per_ant=.25),21),6)
    def test_peace_and_alert_block_birth_below_reserve(self):
        for state in ('Peace','Alert'):
            e=scene(reproduction_enabled=True);c=e.world.colonies[0];c.upgraded=True;c.reserves=11;c.strategic_state=state
            e.reproduction.tick(1)
            self.assertFalse(e.world.ants);self.assertEqual(c.reserves,11)
            c.reserves=12;e.reproduction.tick(2)
            self.assertEqual(len(e.world.ants),1);self.assertEqual(c.reserves,10)
    def test_birth_accounts_for_new_population_reserve(self):
        e=scene(reproduction_enabled=True);c=e.world.colonies[0];c.upgraded=True;c.reserves=12
        for i in range(20):add(e,(15+i,15))
        e.reproduction.tick(1);self.assertEqual(len(e.world.ants),20)
        c.reserves=13;e.reproduction.tick(2)
        self.assertEqual(c.reserves,11);self.assertEqual(c.reserve_target,11)
    def test_paid_upgrade_retains_reserve_and_war_removes_restriction(self):
        e=scene(reproduction_enabled=True);c=e.world.colonies[0];c.reserves=10
        e.reproduction.tick(1);self.assertFalse(c.upgraded)
        c.reserves=20;e.reproduction.tick(2)
        self.assertTrue(c.upgraded);self.assertEqual(c.reserves,10);self.assertFalse(e.world.ants)
    def test_wartime_blocked_spawn_does_not_spend(self):
        e=scene(reproduction_enabled=True);c=e.world.colonies[0]
        c.strategic_state='Total War';c.upgraded=True;c.reserves=10
        for p in e.navigation.home(0):e.world.terrain.set(*p,STONE)
        e.reproduction.tick(1);self.assertFalse(e.world.ants);self.assertEqual(c.reserves,10)
    def test_survival_can_spend_reserved_food(self):
        e=scene();a=add(e);c=e.world.colonies[0];c.reserves=10;c.queen.hp=49
        e.economy.tick(1);self.assertEqual(c.reserves,9);self.assertEqual(c.queen.hp,50)
        e.economy.tick(100);self.assertEqual(c.reserves,8)
    def test_five_consecutive_critical_completed_turns(self):
        e=scene();enemy=add(e,(1,2),1);c=e.world.colonies[0]
        for turn in range(1,5):
            e.combat.refresh();e.strategy.assess(turn);e.strategy.assess(turn)
            self.assertEqual(c.critical_turns,turn);self.assertNotEqual(c.strategic_state,'Total War')
        e.strategy.assess(5);self.assertEqual(c.strategic_state,'Total War')
        self.assertEqual(c.declaration_target,enemy.position)
    def test_isolated_sighting_and_reset(self):
        e=scene();enemy=add(e,(1,2),1);c=e.world.colonies[0];e.combat.refresh();e.strategy.assess(1)
        place(e,enemy,(40,40));e.combat.refresh();e.strategy.assess(2)
        self.assertEqual(c.critical_turns,0);self.assertEqual(c.strategic_state,'Peace')
    def test_low_hp_requires_nearby_enemy_and_strict_threshold(self):
        e=scene();c=e.world.colonies[0];c.queen.hp=14;e.strategy.assess(1)
        self.assertNotEqual(c.strategic_state,'Total War')
        enemy=add(e,(7,3),1);e.combat.refresh();c.queen.hp=15;e.strategy.assess(2)
        self.assertNotEqual(c.strategic_state,'Total War')
        c.queen.hp=14.5;e.strategy.assess(3);self.assertEqual(c.strategic_state,'Total War')
    def test_return_to_peace_after_quiet_recovery(self):
        e=scene();c=e.world.colonies[0];c.strategic_state='Total War';c.declaration_epoch=1
        for t in range(1,10):e.strategy.assess(t);self.assertEqual(c.strategic_state,'Total War')
        e.strategy.assess(10);self.assertEqual(c.strategic_state,'Peace');self.assertEqual(c.declaration_epoch,2)
    def test_communication_advances_one_hop_and_no_enemy_leak(self):
        e=scene();a=add(e,(13,3));b=add(e,(15,3));far=add(e,(30,30));enemy=add(e,(14,3),1)
        c=e.world.colonies[0];c.strategic_state='Total War';c.declaration_epoch=1;c.declaration_target=(8,3)
        e.orders.propagate(1)
        self.assertEqual(a.order_state,'Total War');self.assertEqual(b.order_state,'Peace')
        self.assertEqual(far.order_state,'Peace');self.assertEqual(enemy.order_state,'Peace')
        e.orders.propagate(1);self.assertEqual(b.order_state,'Peace')
        e.orders.propagate(2);self.assertEqual(b.order_state,'Total War');self.assertEqual(b.order_target,(8,3))
        c.strategic_state='Peace';c.declaration_epoch=2;c.declaration_target=None
        e.orders.propagate(3);self.assertEqual(b.order_state,'Total War')
        e.orders.propagate(4);self.assertEqual(b.order_state,'Peace')
    def test_mobilization_uses_received_target_and_keeps_logistics(self):
        e=scene();workers=[add(e,(20+i,20)) for i in range(4)];s=add(e,(25,20),kind='soldier')
        for a in workers+[s]:a.order_state='Total War';a.order_target=(30,20);a.order_epoch=1
        e.orders.propagate(1);e.depots.begin_plan();e.combat.refresh()
        for a in workers+[s]:e.fsm.prepare(a)
        self.assertEqual(s.state,'offensive');self.assertEqual(workers[1].state,'war-support')
        self.assertNotEqual(workers[0].state,'war-support')
    def test_war_food_worker_keeps_harvesting_during_remote_alarm(self):
        e=scene();a=add(e,(20,20));c=e.world.colonies[0]
        c.strategic_state='Total War';c.threat='critical';c.threat_target=(8,3)
        a.order_state='Total War';a.order_target=(8,3);e.orders.logistics={a.id}
        source=Food(e.world.allocate_id(),(21,20),'small',5,4)
        e.world.food.append(source);e.food.rebuild_scent();e.combat.refresh()
        e.depots.begin_plan();e.fsm.prepare(a)
        self.assertEqual(a.state,'seek-food');self.assertEqual(a.target,source.position)
    def test_total_war_affordable_soldiers_and_one_action(self):
        e=scene(reproduction_enabled=True,perks=('warfare',)*4);c=e.world.colonies[0]
        c.upgraded=True;c.strategic_state='Total War';c.reserves=3
        before=e.food.accounting()['residual'];e.reproduction.tick(1);e.reproduction.tick(1)
        self.assertEqual(len(e.world.ants),1);self.assertEqual(e.world.ants[0].kind,'soldier');self.assertEqual(c.reserves,1.5)
        e.reproduction.tick(2);self.assertEqual(c.reserves,0);self.assertEqual(len(e.world.ants),2)
        self.assertEqual(e.food.accounting()['residual'],before)
        c.reserves=-.5;c.bonus_queue=['soldier'];e.reproduction.tick(3);self.assertEqual(len(e.world.ants),2)
    def test_war_upgrade_still_costs_and_takes_turn(self):
        e=scene(reproduction_enabled=True);c=e.world.colonies[0];c.strategic_state='Total War';c.reserves=12
        e.reproduction.tick(1);self.assertTrue(c.upgraded);self.assertFalse(e.world.ants);self.assertEqual(c.reserves,2)
        e.reproduction.tick(2);self.assertEqual(e.world.ants[0].kind,'soldier');self.assertEqual(c.reserves,0)
    def test_queen_death_clears_war_and_blocks_production(self):
        e=scene(reproduction_enabled=True);a=add(e);c=e.world.colonies[0]
        c.strategic_state=a.order_state='Total War';c.reserves=100;c.queen.hp=0
        e.lifecycle.cleanup(1);e.reproduction.tick(2)
        self.assertEqual(c.strategic_state,'Peace');self.assertEqual(a.order_state,'Peace');self.assertEqual(c.reserve_target,0)
        self.assertEqual(len(e.world.ants),1)


