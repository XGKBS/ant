"""V2 replaces old physical-stock assertions with shared-endpoint equivalents.
The unchanged strategy tests remain in test_strategy_depots.py.
"""
import unittest
from dataclasses import asdict
import numpy as np
from entities.models import Food
from simulation.terrain import STONE
from tests.test_strategy_depots import scene, add, place, build


def project(count=2, **options):
    e=scene(**options);c=e.world.colonies[0];c.reserves=30
    j=e.construction.create(0,'depot',(25,25))
    ants=[add(e,p) for p in e.construction.work_cells(j)[:count]]
    for a in ants:a.construction_task=j.id
    j.crew=[a.id for a in ants]
    return e,j,ants


def work(e,j,ants,turn):
    for a in ants:a.action_used=False
    e.construction.resolve(turn)


def deposit(e,d,a,amount=1,turn=20):
    place(e,a,d.position);a.cargo=amount;a.cargo_origin='harvest'
    a.state='deliver-depot';a.depot_id=d.id
    return e.depots.action(a,turn)


class DepotConstructionTests(unittest.TestCase):
    def test_exact_atomic_cost_and_conservation(self):
        e=scene();c=e.world.colonies[0];c.reserves=30;before=e.food.accounting()['residual']
        j=e.construction.create(0,'depot',(25,25))
        self.assertEqual((c.reserves,j.paid_half,c.depot_spent_half),(15,30,30))
        self.assertEqual(e.food.accounting()['residual'],before)
        self.assertFalse(e.depots.commit(j));self.assertEqual(c.reserves,15)
    def test_negative_or_reserved_balance_cannot_pay(self):
        for balance in (-1,0,14,24.5):
            e=scene();e.world.colonies[0].reserves=balance
            self.assertIsNone(e.construction.create(0,'depot',(25,25)))
            self.assertEqual(e.world.colonies[0].reserves,balance)
    def test_war_can_commit_without_reserve_floor(self):
        e=scene();c=e.world.colonies[0];c.reserves=15;c.strategic_state='Total War'
        self.assertIsNotNone(e.construction.create(0,'depot',(25,25)));self.assertEqual(c.reserves,0)
    def test_two_workers_exactly_ten_turns(self):
        e,j,ants=project();soil=e.construction.soil_total();r=e.food.accounting()['residual']
        for turn in range(1,10):
            work(e,j,ants,turn);self.assertEqual(j.progress,2*turn);self.assertFalse(e.world.depots)
        work(e,j,ants,10)
        self.assertEqual(len(e.world.depots),1);self.assertEqual(j.progress,20)
        self.assertEqual(e.world.colonies[0].reserves,15)
        self.assertEqual(e.food.accounting()['residual'],r);self.assertEqual(e.construction.soil_total(),soil)
    def test_three_workers_take_seven_turns(self):
        e,j,ants=project(3)
        for turn in range(1,7):work(e,j,ants,turn)
        self.assertEqual(j.progress,18);self.assertFalse(e.world.depots)
        work(e,j,ants,7);self.assertEqual(len(e.world.depots),1);self.assertEqual(j.progress,21)
    def test_zero_and_one_builder_pause(self):
        for count in (0,1):
            e,j,ants=project(count)
            for t in range(1,12):work(e,j,ants,t)
            self.assertEqual(j.progress,0);self.assertFalse(e.world.depots)
    def test_progress_persists_through_interruption_and_timeout(self):
        e,j,ants=project();work(e,j,ants,1);work(e,j,ants,2)
        ants[1].state='fight';ants[1].combat_target=('ant',999)
        work(e,j,ants,3);self.assertEqual(j.progress,4)
        e.world.turn=50;e.construction.begin_plan();self.assertIn(j.id,e.construction.tasks)
        ants[1].state='build-depot';ants[1].combat_target=None
        j.crew=[a.id for a in ants]
        for a in ants:a.construction_task=j.id
        for t in range(51,59):work(e,j,ants,t)
        self.assertEqual(len(e.world.depots),1)
    def test_duplicate_crew_and_turn_cannot_duplicate_work(self):
        e,j,ants=project();j.crew*=3;work(e,j,ants,1)
        self.assertEqual(j.progress,2)
        for a in ants:a.action_used=False
        e.construction.resolve(1);self.assertEqual(j.progress,2)
        self.assertEqual(j.contributions,{a.id:1 for a in ants})
    def test_action_budget_soldier_and_honeypot_exclusions(self):
        for reason in ('soldier','honeypot','spent','dead'):
            e,j,ants=project();a=ants[1]
            if reason in ('soldier','honeypot'):a.kind=reason
            elif reason=='spent':a.action_used=True
            else:a.hp=0
            e.construction.resolve(1);self.assertEqual(j.progress,0)
    def test_completion_occupancy_recheck_no_second_payment(self):
        e,j,ants=project();blocker=add(e,j.target)
        for t in range(1,11):work(e,j,ants,t)
        self.assertEqual(j.progress,20);self.assertFalse(e.world.depots)
        self.assertIn('footprint',j.blocked_reason)
        place(e,blocker,(40,40));work(e,j,ants,11)
        self.assertEqual(len(e.world.depots),1);self.assertEqual(e.world.colonies[0].depot_spent_half,30)
    def test_invalid_overlap_occupied_and_stone_destinations(self):
        e=scene();d,a=build(e)
        self.assertFalse(e.depots.valid(d.position));self.assertIsNone(e.construction.create(1,'depot',d.position))
        self.assertFalse(e.depots.valid((63,63)));self.assertFalse(e.depots.valid((2,2)))
        add(e,(35,35));self.assertFalse(e.depots.valid((35,35)))
        place(e,a,(23,23));stone=e.construction.stones.register(((24,25),),4)
        self.assertFalse(e.construction.stones.can_move(stone,(1,0)))
    def test_configurable_footprint_and_exclusive_claims(self):
        e=scene(depot_footprint=(3,2));e.world.colonies[0].reserves=30;e.world.colonies[1].reserves=30
        j=e.construction.create(0,'depot',(25,25));self.assertEqual(len(e.world.depot_claims),6)
        self.assertIsNone(e.construction.create(1,'depot',(27,25)))
        e.construction.finish(j);self.assertFalse(e.world.depot_claims)
        self.assertIsNotNone(e.construction.create(1,'depot',(27,25)))
    def test_abandonment_and_queen_death_keep_sunk_cost(self):
        e,j,ants=project();before=e.food.accounting()['residual']
        e.world.colonies[0].queen.hp=0;e.lifecycle.cleanup(1);e.construction.begin_plan()
        self.assertNotIn(j.id,e.construction.tasks);self.assertFalse(e.world.depot_claims)
        self.assertEqual(e.world.colonies[0].depot_spent_half,30)
        self.assertEqual(e.food.accounting()['residual'],before)


class DepotSharedEconomyTests(unittest.TestCase):
    def test_deposit_exact_credit_once_and_no_stock(self):
        e=scene();d,a=build(e);c=e.world.colonies[0];a.cargo=1
        r=e.food.accounting()['residual'];before=c.reserves
        self.assertTrue(deposit(e,d,a));self.assertFalse(e.depots.action(a,20))
        self.assertEqual((a.cargo,c.reserves,d.deposited),(0,before+1,1))
        self.assertNotIn('units',asdict(d));self.assertEqual(c.received_half,2)
        self.assertEqual(e.food.accounting()['residual'],r)
    def test_depot_credit_funds_upgrade_birth_healing_and_upkeep(self):
        e=scene(reproduction_enabled=True);d,a=build(e);c=e.world.colonies[0];c.reserves=19
        deposit(e,d,a);e.reproduction.tick(21)
        self.assertTrue(c.upgraded);self.assertEqual(c.reserves,10)
        c.reserves=11;deposit(e,d,a,turn=22);e.reproduction.tick(22)
        self.assertEqual(c.reserves,10);self.assertEqual(len(e.world.ants),2)
        c.queen.hp=49;deposit(e,d,a,turn=23);e.economy.tick(23)
        self.assertEqual(c.queen.hp,50);self.assertEqual(c.reserves,10)
        e.economy.tick(100);self.assertEqual(c.reserves,8)
    def test_war_uses_depot_credit_and_preserves_production_limit(self):
        e=scene(reproduction_enabled=True);d,a=build(e);c=e.world.colonies[0]
        c.reserves=1;c.upgraded=True;c.strategic_state='Total War'
        deposit(e,d,a);e.reproduction.tick(20);e.reproduction.tick(20)
        self.assertEqual(c.produced_soldiers,1);self.assertEqual(c.reserves,0)
    def test_friendly_only_and_soldiers_never_deliver_or_withdraw(self):
        e=scene();d,a=build(e);c=e.world.colonies[0];before=c.reserves
        for kind,faction in (('soldier',0),('honeypot',0),('worker',1)):
            b=add(e,(26,25),faction,kind);b.cargo=0 if kind=='honeypot' else 1
            b.state='deliver-depot';b.depot_id=d.id
            self.assertFalse(e.depots.action(b,20))
        self.assertEqual(c.reserves,before);self.assertEqual(d.deposited,0)
    def test_personal_rations_and_soil_are_not_duplicated(self):
        e=scene();d,a=build(e);place(e,a,d.position);a.cargo=1;a.cargo_origin='ration';a.state='deliver-depot';a.depot_id=d.id
        r=e.food.accounting()['residual'];self.assertFalse(e.depots.action(a,99))
        before=e.world.colonies[0].reserves;e.economy.tick(100)
        self.assertEqual(a.cargo,0);self.assertEqual(e.world.colonies[0].reserves,before)
        self.assertEqual(e.food.accounting()['residual'],r)
    def test_queenless_endpoint_disconnects_no_healing_or_credit(self):
        e=scene();d,a=build(e);c=e.world.colonies[0];c.queen.hp=0;e.lifecycle.cleanup(1)
        a.hp=3;deposit(e,d,a);balance=c.reserves
        self.assertFalse(e.depots.connected(d));self.assertEqual(a.cargo,1)
        self.assertFalse(e.depots.prepare_healing(a));self.assertEqual(c.reserves,balance)
        e.fsm.resolve_action(a,21);self.assertEqual(a.hp,4);self.assertEqual(a.cargo,0)
    def test_queenless_still_seeks_real_food(self):
        e=scene();d,a=build(e);e.world.colonies[0].queen.hp=0;e.lifecycle.cleanup(0)
        place(e,a,(26,25));a.hp=3;a.depot_id=d.id
        source=Food(e.world.allocate_id(),(29,25),'small',5,4,age=4)
        e.world.food.append(source);a.known_food[source.id]=source.position
        e.combat.refresh();e.fsm.prepare(a);self.assertEqual(a.target,source.position)
    def test_delivery_uses_actual_route_cost_not_geometric_distance(self):
        e=scene();d,a=build(e,(20,10));place(e,a,(18,10));a.cargo=1
        for y in range(45):e.world.terrain.set(19,y,STONE)
        for turn in range(1,100):
            e.navigation.begin_turn(turn);e.depots.destination(a)
            if a.state!='delivery-plan':break
        self.assertEqual(a.state,'return-base')
    def test_completed_depot_redirects_carrier_without_haulers(self):
        e=scene();d,a=build(e);place(e,a,(24,24));a.cargo=1;e.depots.begin_plan()
        for t in range(1,20):
            e.navigation.begin_turn(t);e.depots.destination(a)
            if a.state!='delivery-plan':break
        self.assertEqual(a.state,'deliver-depot');self.assertFalse(e.depots.logistics_workers)
    def test_depot_receipts_are_observational_not_remote_stock(self):
        a,b=scene(),scene()
        for e in (a,b):
            d,worker=build(e);place(e,worker,(40,40));worker.cargo=1
        b.world.depots[0].deposited=100
        for t in range(1,8):
            for e in (a,b):e.navigation.begin_turn(t);e.depots.prepare(e.world.ants[0])
        self.assertEqual(a.world.ants[0].target,b.world.ants[0].target)
    def test_heavy_lifting_fractional_delivery_and_perk_loss(self):
        e=scene(perks=('heavy-lifting',)*4);d,a=build(e);a.cargo=1.5
        before=e.food.accounting()['residual'];balance=e.world.colonies[0].reserves
        deposit(e,d,a,1.5);self.assertEqual(e.world.colonies[0].reserves,balance+1.5)
        self.assertEqual(e.food.accounting()['residual'],before)
        a.cargo=1.5;e.world.colonies[0].queen.hp=0;r=e.food.accounting()['residual'];e.lifecycle.cleanup(30)
        self.assertEqual(a.cargo,1);self.assertEqual(e.food.accounting()['residual'],r)
    def test_signed_shortfall_after_delivery_and_upkeep(self):
        e=scene();d,a=build(e);c=e.world.colonies[0];c.reserves=-1
        deposit(e,d,a);e.economy.tick(100)
        self.assertEqual(c.reserves,-1);e.economy.tick(101);self.assertEqual(c.queen.hp,49)
    def test_direct_queen_delivery_remains_physical(self):
        e=scene();a=add(e);c=e.world.colonies[0];a.cargo=1
        place(e,a,e.fsm.base_cells(a)[0]);r=e.food.accounting()['residual'];e.fsm.resolve_action(a,1)
        self.assertEqual((a.cargo,c.reserves),(0,1));self.assertEqual(e.food.accounting()['residual'],r)

class DepotAutonomyTests(unittest.TestCase):
    def test_no_hidden_food_or_stock_in_planning(self):
        a,b=scene(),scene()
        for e in (a,b):
            e.world.colonies[0].reserves=40
            for p in ((10,10),(11,10),(12,10)):add(e,p)
        b.world.food.append(Food(b.world.allocate_id(),(40,40),'large',25,16))
        for t in range(1,41):
            for e in (a,b):
                e.world.turn=t;e.navigation.begin_turn(t);e.depots.propose(e.world.ants[0],e.construction)
        self.assertFalse(a.construction.tasks);self.assertFalse(b.construction.tasks)
        self.assertEqual(a.depots.savings,b.depots.savings)
    def test_useful_observed_site_recruits_and_builds(self):
        e=scene();e.world.colonies[0].reserves=30
        for p in ((30,30),(34,30)):e.world.food.append(Food(e.world.allocate_id(),p,'large',25,16,age=16))
        for p in ((29,30),(29,31),(30,32),(32,30)):add(e,p)
        r=e.food.accounting()['residual'];soil=e.construction.soil_total();e.food.rebuild_scent();e._plan()
        for _ in range(100):
            e.advance(1)
            self.assertEqual(e.food.accounting()['residual'],r)
            self.assertEqual(e.construction.soil_total(),soil)
            self.assertTrue(np.all(e.world.terrain.occupancy<=e.world.terrain.capacity))
        self.assertGreater(e.depots.completed,0)
        self.assertGreater(sum(d.deposited for d in e.world.depots),0)
        done=[v for v in e.depots.events if v['kind']=='completed']
        self.assertGreaterEqual(len(done[0]['builders']),2)
        self.assertLessEqual(len([v for v in e.depots.events if v['kind']=='accepted']),3)
    def test_dangerous_site_is_not_committed(self):
        e=scene();e.world.colonies[0].reserves=30
        ants=[add(e,p) for p in ((29,30),(29,31),(30,32))]
        ants[0].food_observations={1:((30,30),25,'large',0,True)}
        for a in ants:a.foreign_target=(30,30)
        for t in range(1,50):e.world.turn=t;e.navigation.begin_turn(t);e.depots.propose(ants[0],e.construction)
        self.assertFalse(e.construction.tasks);self.assertGreater(e.depots.failures['observed danger'],0)
    def test_unreachable_site_is_not_committed(self):
        e=scene();e.world.colonies[0].reserves=30;ants=[add(e,p) for p in ((10,10),(11,10),(12,10))]
        ants[0].food_observations={1:((40,40),25,'large',0,True)}
        for y in range(64):e.world.terrain.set(32,y,STONE)
        for t in range(1,50):e.world.turn=t;e.navigation.begin_turn(t);e.depots.propose(ants[0],e.construction)
        self.assertFalse(e.construction.tasks)
    def test_recruitment_leaves_harvesters_and_persists(self):
        e,j,ants=project();extra=[add(e,p) for p in ((28,25),(28,26),(29,25),(29,26))]
        for t in range(1,3):
            e.world.turn=t;e.navigation.begin_turn(t);e.construction.begin_plan()
        self.assertGreaterEqual(len(j.crew),2);self.assertLess(len(j.crew),len(e.world.ants));self.assertLessEqual(len(j.crew),4)
        member=next(a for a in e.world.ants if a.id in j.crew);member.state='fight';member.combat_target=('ant',999)
        e.construction.begin_plan();self.assertIn(member.id,j.crew)
        member.combat_target=None;e.fsm.prepare(member);self.assertEqual(member.state,'build-depot')
    def test_low_priority_exploration_does_not_steal_builders(self):
        e,j,ants=project();add(e,(40,40))
        for a in ants:a.target=e.construction.work_cells(j)[0]
        e.exploration.roles={ants[0].id:'central-expedition'}
        for a in ants:e.fsm.prepare(a);self.assertEqual(a.state,'build-depot')
    def test_savings_is_policy_not_inventory_and_war_overrides_it(self):
        e=scene(reproduction_enabled=True);c=e.world.colonies[0];c.reserves=24;c.upgraded=True
        e.depots.savings[0]=((25,25),150);r=e.food.accounting()['residual']
        e.reproduction.tick(1);self.assertFalse(e.world.ants);self.assertEqual(c.reserves,24)
        c.strategic_state='Total War';e.reproduction.tick(2)
        self.assertEqual(c.produced_soldiers,1);self.assertEqual(e.food.accounting()['residual'],r)
    def test_expired_savings_releases_production(self):
        e=scene(reproduction_enabled=True);c=e.world.colonies[0];c.upgraded=True;c.reserves=20
        e.depots.savings[0]=((25,25),10);e.world.turn=10;e.depots.begin_plan();e.reproduction.tick(10)
        self.assertEqual(c.produced_workers,1);self.assertFalse(e.depots.savings)
    def test_replay_render_pause_reset_cap_and_end(self):
        import os
        os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
        import pygame
        from config import Config
        from simulation.engine import Engine
        from benchmarks.honeypots import fingerprint
        from ui.renderer import Renderer
        pygame.init();screen=pygame.display.set_mode((1100,800))
        a,b=Engine(Config(size=64,max_turns=65)),Engine(Config(size=64,max_turns=65));r=Renderer(screen,b)
        r.overlays.enabled.update(scent=True,pheromones=True,territory=True)
        for t in range(65):
            a.advance(1);b.paused=True;b.advance(10);b.paused=False;b.advance(.25);b.advance(.75)
            if t%10==0:
                before=fingerprint(b);r.focus(b,0);r.draw(b);r.overview();r.draw(b);self.assertEqual(fingerprint(b),before)
            self.assertEqual(fingerprint(a),fingerprint(b))
        self.assertTrue(a.ended);before=fingerprint(a);a.advance(10);self.assertEqual(fingerprint(a),before)
        a.reset();self.assertEqual(fingerprint(a),fingerprint(Engine(a.config)));a.end();self.assertTrue(a.ended)
        pygame.quit()
    def test_site_and_depot_inspection_are_observational(self):
        import os
        os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
        import pygame
        from benchmarks.honeypots import fingerprint
        from ui.renderer import Renderer
        pygame.init();screen=pygame.display.set_mode((1100,800));e,j,ants=project()
        r=Renderer(screen,e);before=fingerprint(e);r.inspect(e,r.point(e,j.target));self.assertEqual(r.selected_site,j.id);r.draw(e)
        self.assertEqual(fingerprint(e),before)
        for t in range(1,11):work(e,j,ants,t)
        d=e.world.depots[0];r.inspect(e,r.point(e,d.position));self.assertEqual(r.selected_depot,d.id);r.draw(e)
        e.reset();r.rebuild(e);self.assertIsNone(r.selected_depot);self.assertIsNone(r.selected_site);pygame.quit()

class DepotSchedulingRegressionTests(unittest.TestCase):
    def test_assigned_carrier_finishes_delivery_before_building(self):
        e,j,ants=project();add(e,(40,40));a=ants[0];a.cargo=1
        e.navigation.begin_turn(1);e.fsm.prepare(a);e.construction.recruit(j)
        self.assertEqual(a.construction_task,j.id);self.assertEqual(a.cargo,1)
        self.assertNotEqual(a.state,'build-depot')
        place(e,a,e.fsm.base_cells(a)[0]);e.fsm.resolve_action(a,1)
        self.assertEqual(a.cargo,0);e.fsm.prepare(a)
        self.assertEqual(a.state,'build-depot');self.assertEqual(a.construction_task,j.id)
    def test_two_surviving_workers_do_not_reduce_to_one_builder(self):
        e,j,ants=project();e.construction.begin_plan()
        self.assertEqual(set(j.crew),{a.id for a in ants})
    def test_invalid_single_capacity_approach_rejected_without_payment(self):
        e=scene();e.world.colonies[0].reserves=30
        cells=e.depots.cells((25,25))
        approaches={p for c in cells for p in ((c[0]-1,c[1]),(c[0]+1,c[1]),(c[0],c[1]-1),(c[0],c[1]+1)) if p not in cells}
        for p in sorted(approaches)[1:]:e.world.terrain.set(*p,STONE)
        self.assertIsNone(e.construction.create(0,'depot',(25,25)))
        self.assertEqual(e.world.colonies[0].reserves,30)
    def test_completed_destination_reacts_to_changed_topology(self):
        e=scene();d,a=build(e,(20,10));place(e,a,(18,10));a.cargo=1
        for t in range(1,6):e.navigation.begin_turn(t);e.depots.destination(a)
        self.assertEqual(a.state,'deliver-depot')
        for y in range(45):e.world.terrain.set(19,y,STONE)
        for t in range(6,20):
            e.navigation.begin_turn(t);e.depots.destination(a)
            if a.state!='delivery-plan':break
        self.assertEqual(a.state,'return-base')

    def test_queen_death_cancels_before_same_turn_construction_actions(self):
        e,j,ants=project();e.world.colonies[0].queen.hp=0;e.lifecycle.cleanup(1)
        e.construction.resolve(1)
        self.assertNotIn(j.id,e.construction.tasks);self.assertEqual(j.progress,0)
        self.assertFalse(any(a.action_used for a in ants));self.assertEqual(e.world.colonies[0].depot_spent_half,30)
