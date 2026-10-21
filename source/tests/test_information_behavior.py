"""Physical universal information sharing and bounded useful behavior."""
import unittest
from dataclasses import replace
import numpy as np
from entities.models import Food
from tests.test_strategy_depots import scene,add,place,build
from simulation.spatial import SpatialIndex
from simulation.terrain import SOIL,PASSAGE,STONE


def relay(e,turn):
    e.world.turn=turn;e.combat.refresh();e.orders.propagate(turn,e.combat.index)


class InformationTests(unittest.TestCase):
    def test_soldier_discovers_food_and_physically_informs_worker(self):
        e=scene(information_interval=1);s=add(e,(20,20),kind='soldier');w=add(e,(18,20))
        f=Food(e.world.allocate_id(),(21,20),'small',5,4);e.world.food.append(f)
        e.combat.refresh();e.fsm.prepare(s);e.fsm.prepare(w)
        self.assertIn(f.id,s.known_food);self.assertNotIn(f.id,w.known_food)
        relay(e,1);self.assertEqual(w.known_food[f.id],f.position)
        e.fsm.prepare(w);self.assertEqual(w.target,f.position);self.assertEqual(w.state,'seek-food')
        self.assertEqual(s.cargo,0)
    def test_received_food_discovery_results_in_real_harvest_delivery(self):
        e=scene(information_interval=1);s=add(e,(20,20),kind='soldier');w=add(e,(18,20))
        f=Food(e.world.allocate_id(),(21,20),'small',5,4);e.world.food.append(f)
        initial=e.food.accounting()['residual'];soil=e.construction.soil_total();e.food.rebuild_scent();e._plan()
        for _ in range(45):
            e.advance(1);self.assertEqual(e.food.accounting()['residual'],initial)
            self.assertEqual(e.construction.soil_total(),soil)
        self.assertGreater(e.food.delivered,0);self.assertGreater(e.information.metrics['relayed_food'],0)
    def test_worker_warning_reaches_soldier_without_live_enemy_tracking(self):
        e=scene(information_interval=1,combat_enabled=True,perks=('sensitivity',)*4)
        w=add(e,(20,20));s=add(e,(18,20),kind='soldier');enemy=add(e,(23,20),1)
        e.combat.refresh();e.fsm.prepare(w);self.assertEqual(w.combat_target,('ant',enemy.id))
        relay(e,1);place(e,enemy,(50,50));e.combat.refresh();e.fsm.prepare(s)
        self.assertEqual(s.state,'investigate');self.assertEqual(s.target,(23,20));self.assertIsNone(s.combat_target)
    def test_multihop_does_not_flood_chain_in_one_turn(self):
        e=scene(information_interval=1);a=add(e,(20,20));b=add(e,(22,20),kind='soldier');c=add(e,(24,20),kind='honeypot');far=add(e,(40,40))
        e.information.publish(a,'food',99,(19,20),(5,'small',True))
        relay(e,1);self.assertIn(99,b.known_food);self.assertNotIn(99,c.known_food);self.assertNotIn(99,far.known_food)
        relay(e,2);self.assertIn(99,c.known_food);self.assertNotIn(99,far.known_food)
    def test_all_unit_types_discover_and_relay_all_fact_types(self):
        for kind in ('worker','soldier','honeypot'):
            e=scene(information_interval=1);a=add(e,(20,20),kind=kind);b=add(e,(22,20))
            f=Food(999,(20,21),'small',5,4);e.world.food.append(f);e.combat.refresh();e.fsm.prepare(a)
            for category in ('enemy','danger','route','excavation','supply'):
                e.information.publish(a,category,category,(21,20),(1,))
            for turn in range(1,10):relay(e,turn)
            self.assertIn(f.id,b.known_food)
            self.assertTrue({'food','enemy','danger','route','excavation','supply'}.issubset({f.kind for f in b.information.values()}))
            if kind=='honeypot':self.assertEqual(a.cargo,0);self.assertEqual(a.damage,0)
    def test_enemy_faction_never_receives_facts(self):
        e=scene(information_interval=1);a=add(e,(20,20));foe=add(e,(21,20),1)
        e.information.publish(a,'food',99,(20,21),(5,'small',True));relay(e,1)
        self.assertNotIn(99,foe.known_food);self.assertFalse(foe.information)
    def test_unchanged_facts_do_not_cause_communication_storm(self):
        e=scene(information_interval=1);a=add(e,(20,20));b=add(e,(22,20));c=add(e,(24,20))
        e.information.publish(a,'food',99,(19,20),(5,'small',True))
        for turn in range(1,10):relay(e,turn)
        count=e.information.metrics['received']
        for turn in range(10,90):relay(e,turn)
        self.assertEqual(count,2);self.assertEqual(e.information.metrics['received'],count)
    def test_memory_and_global_event_limits(self):
        e=scene(information_interval=1,information_capacity=6,information_events_per_turn=3)
        ants=[add(e,(20+i%4,20+i//4)) for i in range(12)]
        for a in ants:
            for ident in range(40):e.information.publish(a,'food',a.id*100+ident,(20,20),(5,'small',True))
            self.assertLessEqual(len(a.information),6);self.assertLessEqual(len(a.information_seen),12)
            self.assertLessEqual(len(a.known_food),12);self.assertLessEqual(len(a.food_observations),12)
        relay(e,1);self.assertLessEqual(e.information.last_events,3)
        self.assertLessEqual(e.information.metrics['events_peak'],3)
    def test_bounded_spatial_probes_rotate_through_crowds(self):
        e=scene();ants=[add(e,(20+i%8,20+i//8)) for i in range(64)]
        index=SpatialIndex(ants);p=(26,26);seen=set()
        for offset in range(256):
            batch=list(index.near_limited(p,2,4,offset));self.assertLessEqual(len(batch),4);seen.update(a.id for a in batch)
        expected={a.id for a in ants if abs(a.position[0]-26)+abs(a.position[1]-26)<=2}
        self.assertTrue(expected.issubset(seen))
    def test_expired_food_and_enemy_information_stops_guidance(self):
        e=scene(information_interval=1);a=add(e,(20,20))
        e.information.publish(a,'food',99,(30,30),(5,'small',True));e.information.publish(a,'enemy',('ant',100),(24,20),(1,))
        relay(e,129);self.assertFalse(a.information);self.assertNotIn(99,a.known_food)
    def test_latest_observed_version_wins_without_hidden_stock(self):
        e=scene(information_interval=1);a=add(e,(20,20));b=add(e,(22,20))
        e.information.publish(a,'food',99,(19,20),(5,'small',True));relay(e,1)
        e.world.turn=5;e.information.publish(a,'food',99,(19,20),(0,'small',True));relay(e,6)
        self.assertNotIn(99,b.known_food);self.assertEqual(b.food_observations[99][1],0)
    def test_queenless_units_relay_without_restoring_queen_strategy(self):
        e=scene(information_interval=1);a=add(e,(20,20));b=add(e,(22,20),kind='soldier')
        e.world.colonies[0].queen.hp=0;e.lifecycle.cleanup(1)
        e.information.publish(a,'food',99,(19,20),(5,'small',True));relay(e,2)
        self.assertIn(99,b.known_food);self.assertEqual(b.order_state,'Peace');self.assertEqual(e.world.colonies[0].reserve_target,0)
    def test_depot_planning_does_not_pool_remote_discoveries_instantly(self):
        e=scene();a=add(e,(20,20));b=add(e,(45,45));e.world.colonies[0].reserves=40
        e.information.publish(a,'food',99,(20,21),(25,'large',True));e.depots.observe(a)
        self.assertNotIn(99,b.food_observations);self.assertFalse(e.depots.known)


class UsefulBehaviorTests(unittest.TestCase):
    def test_soldier_patrol_is_committed_and_bounded(self):
        e=scene();s=add(e,(20,20),kind='soldier');e.behavior.begin_plan();e.fsm.prepare(s)
        self.assertIn(s.state,('patrol-route','escort','guard'))
        target=s.target
        for turn in range(1,5):e.world.turn=turn;e.fsm.prepare(s);self.assertEqual(s.target,target)
    def test_guard_holds_position_and_is_not_unproductive(self):
        e=scene();ants=[add(e,(15+i,15),kind='soldier') for i in range(4)]
        e.behavior.begin_plan();a=ants[0];e.fsm.prepare(a);self.assertEqual(a.state,'guard')
        place(e,a,a.target);e.behavior.record(a,1)
        self.assertEqual(a.activity,'strategic_stationary');self.assertEqual(a.unproductive_idle_turns,0)
        self.assertEqual(e.behavior.step(a,a.position),a.position)
    def test_guard_and_patrol_never_override_active_defense(self):
        e=scene();s=add(e,(20,20),kind='soldier');c=e.world.colonies[0];c.threat='critical';c.threat_target=(8,3)
        e.behavior.begin_plan();e.fsm.prepare(s);self.assertEqual(s.state,'defend')
    def test_idle_worker_chooses_unvisited_local_frontier(self):
        e=scene(exploration_enabled=False);a=add(e,(20,20));e.behavior.begin_plan();e.fsm.prepare(a)
        self.assertEqual(a.state,'frontier-local');self.assertNotEqual(a.target,a.position)
        p=e.behavior.step(a,a.position);self.assertLess(abs(p[0]-a.target[0])+abs(p[1]-a.target[1]),abs(a.position[0]-a.target[0])+abs(a.position[1]-a.target[1]))
    def test_no_pointless_excavation_during_idle_planning(self):
        e=scene(exploration_enabled=False);a=add(e,(20,20));soil=e.construction.soil_total();before=e.world.terrain.excavated_units
        e.behavior.begin_plan();e.fsm.prepare(a);e.fsm.choose(a,a.position);e.fsm.resolve_action(a,1)
        self.assertEqual(e.world.terrain.excavated_units,before);self.assertEqual(e.construction.soil_total(),soil)
    def test_automatic_fill_never_narrows_an_existing_passage(self):
        e=scene();a=add(e,(7,5));e.world.terrain.dig(7,6)
        self.assertEqual(e.world.terrain.capacity[6,7],4)
        self.assertNotIn((7,6),e.construction.fill_targets(a.position,0))
    def test_low_priority_assignment_and_retry_budgets(self):
        e=scene(idle_assignments_per_turn=3,idle_path_retries_per_turn=1)
        ants=[add(e,(20+i%10,20+i//10),kind='soldier') for i in range(50)]
        e.behavior.begin_plan()
        for a in ants:e.behavior.prepare(a,True)
        self.assertLessEqual(e.behavior.assignments,3)
        for a in ants:
            if a.target is None:a.target=(63,63)
            for p in ((a.position[0]+1,a.position[1]),(a.position[0],a.position[1]+1)):
                if p[0]<64 and p[1]<64:e.world.terrain.set(*p,STONE)
            e.behavior.step(a,a.position)
        self.assertLessEqual(e.behavior.retries,1)
    def test_graceful_population_planning_interval(self):
        e=scene(idle_population_threshold=10);a=add(e,(20,20))
        for i in range(10):add(e,(30+i,30))
        due=[]
        for t in range(32):e.world.turn=t;due.append(e.behavior.due(a))
        self.assertEqual(sum(due),2)
    def test_activity_keeps_idle_separate_from_stationary(self):
        e=scene();a=add(e);a.state='explore';a.target=None;a.moved_this_turn=False
        e.behavior.record(a,1);self.assertEqual((a.stationary_turns,a.unproductive_idle_turns),(1,1))
        a.state='guard';e.behavior.record(a,2)
        self.assertEqual((a.stationary_turns,a.unproductive_idle_turns),(2,1))
    def test_queen_distance_optimization_is_exact(self):
        for x in range(-8,9):
            for y in range(-8,9):
                d=(-x if x<0 else x-1 if x>1 else 0)+(-y if y<0 else y-1 if y>1 else 0)
                self.assertEqual(d,min(abs(x-a)+abs(y-b) for a,b in ((0,0),(1,0),(0,1),(1,1))))

class CoordinationIntegrationTests(unittest.TestCase):
    def test_received_useful_bottleneck_is_excavated_once(self):
        e=scene();a=add(e,(20,20));target=(21,20);e.world.terrain.traffic[20,21]=8
        e.information.publish(a,'excavation',target,target,(8,1))
        e.world.turn=(-a.id)%e.config.idle_planning_interval;e.behavior.begin_plan()
        soil=e.construction.soil_total();self.assertTrue(e.construction.prepare_idle(a))
        self.assertEqual(a.dig_target,target);e.fsm.resolve_action(a,1)
        self.assertEqual(e.world.terrain.capacity[20,21],4);self.assertEqual(e.construction.soil_total(),soil)
        a.action_used=False;a.soil_cargo=0;e.world.terrain.deposit(a.position,1)
        a.last_action=None;e.construction.prepare_idle(a)
        self.assertEqual(e.world.terrain.excavated_units,1)
    def test_bottleneck_rumor_does_not_justify_unused_soil_digging(self):
        e=scene();a=add(e,(20,20));e.information.publish(a,'excavation',(21,20),(21,20),(8,1))
        e.world.turn=(-a.id)%e.config.idle_planning_interval;e.behavior.begin_plan()
        self.assertFalse(e.construction.prepare_idle(a));self.assertIsNone(a.dig_target)
    def test_exploration_keeps_committed_scout_after_birth(self):
        e=scene(exploration_start_turn=0)
        for i in range(5):add(e,(20+i,20))
        e._plan();scout=next(a for a in e.world.ants if a.id in e.exploration.roles)
        old=scout.id;e.world.turn=1;add(e,(30,20));e.exploration.begin_plan()
        self.assertIn(old,e.exploration.roles)
    def test_new_exploration_assignments_are_bounded(self):
        e=scene(exploration_start_turn=0,idle_assignments_per_turn=3)
        for i in range(100):add(e,(20+i%20,20+i//20))
        e.exploration.roles.clear();e.exploration.begin_plan();self.assertLessEqual(len(e.exploration.roles),3)
    def test_local_information_and_activity_replay(self):
        from benchmarks.honeypots import fingerprint
        from simulation.engine import Engine
        from config import Config
        a,b=Engine(Config(size=64)),Engine(Config(size=64))
        for _ in range(120):
            a.advance(1);b.paused=True;b.advance(9);b.paused=False;b.advance(.25);b.advance(.75)
            self.assertEqual(fingerprint(a),fingerprint(b))
        a.reset();self.assertEqual(fingerprint(a),fingerprint(Engine(a.config)))

    def test_uncommunicated_faction_survey_does_not_change_frontier_target(self):
        a,b=scene(exploration_start_turn=0),scene(exploration_start_turn=0)
        for e in (a,b):
            for i in range(6):add(e,(20+i,20))
        b.exploration.frontiers[0]={(50,50),(55,55)}
        for e in (a,b):e.exploration.begin_plan()
        self.assertEqual(a.exploration.routes,b.exploration.routes)

    def test_depletion_is_observed_and_relayed_without_cargo_duplication(self):
        e=scene(information_interval=1);a=add(e,(20,20));b=add(e,(22,20))
        f=Food(999,(20,21),'small',1,4);e.world.food.append(f);e.combat.refresh();e.fsm.prepare(a)
        relay(e,1);self.assertIn(f.id,b.known_food)
        e.world.turn=2;e.food.harvest(f,2,1);e.fsm.prepare(a);relay(e,3)
        self.assertNotIn(f.id,b.known_food);self.assertEqual(b.food_observations[f.id][1],0)
    def test_identical_content_versions_do_not_trigger_rebroadcast(self):
        e=scene(information_interval=1);a=add(e,(20,20));b=add(e,(22,20))
        e.information.publish(a,'route',(20,21),(20,21),(4,));relay(e,1)
        before=e.information.metrics['received']
        # A second observer version of exactly the same route is not a new message.
        from systems.information import Fact
        a.information[('route',(20,21))]=Fact('route',(20,21),(20,21),(4,),2,a.id,130)
        relay(e,2);self.assertEqual(e.information.metrics['received'],before)
    def test_proven_near_depot_skips_unnecessary_remote_searches(self):
        e=scene();far,a=build(e,(40,40));near,a=build(e,(20,20));place(e,a,near.position);a.cargo=1
        calls=[];original=e.navigation.region_cost
        def cost(key,seeds,position):
            calls.append(key)
            if key==('depot',far.id):return None
            return original(key,seeds,position)
        e.navigation.region_cost=cost;e.depots.destination(a)
        self.assertEqual(a.depot_id,near.id);self.assertEqual(a.state,'deliver-depot')
        self.assertNotIn(('depot',far.id),calls);self.assertNotIn(('home',0),calls)

    def test_uncommunicated_remote_danger_does_not_enter_depot_planner(self):
        e=scene();proposer=add(e,(20,20));observer=add(e,(40,40));add(e,(25,25))
        e.world.colonies[0].reserves=40;observer.foreign_target=(30,30)
        proposer.food_observations={99:((30,30),25,'large',0,True)}
        for turn in range(1,50):
            e.world.turn=turn;e.navigation.begin_turn(turn);e.depots.propose(proposer,e.construction)
        self.assertEqual(e.depots.failures['observed danger'],0)

    def test_default_sending_phase_rotates_across_crowded_bucket_boundaries(self):
        e=scene(information_probe_limit=4)
        for i in range(64):add(e,(16+i%8,16+i//8),1)
        sender=add(e,(25,24));receiver=add(e,(26,24))
        e.information.publish(sender,'food',999,(25,25),(5,'small',True))
        for turn in range(1,33):relay(e,turn)
        self.assertIn(999,receiver.known_food)
