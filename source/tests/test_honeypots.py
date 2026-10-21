from dataclasses import asdict
"""Confirmed Honeypot attributes, finite physical supply and non-omniscient scouting."""
import unittest
from dataclasses import replace
import numpy as np
from entities.models import Ant,Food
from config import Config,PERKS
from systems.perks import movement,load,cost_half
from systems.economy import food_upkeep
from tests.test_strategy_depots import scene,add,place,build


def honey(e,p=(25,25),units=0,faction=0):
    a=Ant(e.world.allocate_id(),faction,p,kind='honeypot',stored_food=units)
    a.path=[p];e.world.ants.append(a);e.world.terrain.occupancy[p[1],p[0]]+=1
    return a


def source(e,p=(25,25),units=5,tier='small'):
    f=Food(e.world.allocate_id(),p,tier,units,4,age=4)
    e.world.food.append(f)
    return f


class DirectConsumptionTests(unittest.TestCase):
    def test_source_first_leaves_worker_cargo_and_supplier_unchanged(self):
        e=scene();a=add(e,(25,25));a.cargo=1;f=source(e);h=honey(e,(26,25),3)
        c=e.world.colonies[0];c.reserves=5;before=e.food.accounting()['residual']
        e.economy.tick(100)
        self.assertEqual((f.units,a.cargo,h.stored_food,c.reserves),(4,1,3,5))
        self.assertEqual(c.upkeep_source_half,2);self.assertEqual(e.food.accounting()['residual'],before)
    def test_soldier_direct_consumption_without_transport(self):
        e=scene();a=add(e,(25,25),kind='soldier');f=source(e,units=1)
        e.economy.tick(100)
        self.assertEqual(a.cargo,0);self.assertEqual(f.units,0);self.assertEqual(f.respawn_deadline,125)
        self.assertEqual(e.world.colonies[0].reserves,0)
    def test_partial_priority_across_all_payment_sources(self):
        e=scene()
        for i in range(50):add(e,(10+i%20,10+i//20))
        a=add(e,(30,30));a.cargo=.5;f=source(e,(30,30),.5);h=honey(e,(31,30),.5)
        c=e.world.colonies[0];c.reserves=50.5;before=e.food.accounting()['residual'];e.economy.tick(100)
        self.assertEqual((f.units,h.stored_food,a.cargo,c.reserves),(0,0,0,0))
        self.assertEqual((c.upkeep_source_half,c.upkeep_honeypot_half,c.upkeep_personal_half,c.upkeep_shared_half),(1,1,1,101))
        self.assertEqual(c.last_upkeep,52);self.assertEqual(e.food.accounting()['residual'],before)
    def test_debt_and_starvation_penalties_remain(self):
        e=scene();a=add(e,(25,25));f=source(e,units=.5);c=e.world.colonies[0]
        e.economy.tick(100);self.assertEqual(c.reserves,-.5);self.assertEqual(c.queen.hp,50)
        e.economy.tick(101);self.assertEqual(c.queen.hp,49)
    def test_supply_radius_faction_and_dead_supplier(self):
        for x,faction,hp,expected in ((35,0,15,0),(36,0,15,-1),(26,1,15,-1),(26,0,0,-1)):
            with self.subTest(x=x,faction=faction,hp=hp):
                e=scene();a=add(e,(25,25));h=honey(e,(x,25),2,faction);h.hp=hp
                e.economy.tick(100);self.assertEqual(e.world.colonies[0].reserves,expected)
                self.assertEqual(h.stored_food,1 if expected==0 else 2)
    def test_nearest_supplier_then_id_and_multiple_partial_suppliers(self):
        e=scene();a=add(e,(25,25));a.cargo=1
        far=honey(e,(28,25),3);near=honey(e,(26,25),.5);tie=honey(e,(25,26),3)
        before=e.food.accounting()['residual'];e.economy.tick(100)
        self.assertEqual((near.stored_food,tie.stored_food,far.stored_food,a.cargo),(0,2.5,3,1))
        self.assertEqual(e.food.accounting()['residual'],before)
    def test_settlement_order_is_stable_ant_id(self):
        e=scene();a=add(e,(25,25));b=add(e,(26,25));a.cargo=b.cargo=1;h=honey(e,(25,26),1)
        e.world.ants.reverse();e.economy.tick(100)
        self.assertEqual(a.cargo,1);self.assertEqual(b.cargo,0);self.assertEqual(h.stored_food,0)
    def test_zero_upkeep_does_not_consume_source_or_storage(self):
        e=scene();h=honey(e,units=10);f=source(e,units=1)
        e.economy.tick(100);e.economy.tick(100)
        self.assertEqual((h.stored_food,f.units,e.world.colonies[0].reserves),(10,1,0))
        self.assertEqual(e.world.colonies[0].last_upkeep,0)
    def test_honeypot_does_not_raise_ordinary_progressive_bracket(self):
        e=scene()
        for i in range(50):add(e,(10+i%20,10+i//20))
        h=honey(e,(60,50),10);e.economy.tick(100)
        self.assertEqual(e.world.colonies[0].last_upkeep,50);self.assertEqual(h.stored_food,10)
    def test_source_consumption_respects_station_refill_and_no_greed_collection(self):
        e=scene(supply_stations_enabled=True,perks=('greed',)*4);e.supply.tick(75);s=e.world.stations[0];s.units=.5
        a=add(e,s.position);e.economy.tick(100)
        self.assertEqual(s.units,0);self.assertIsNone(s.respawn_deadline)
        self.assertFalse(e.world.colonies[0].greed_seen)
        e.supply.tick(100);self.assertEqual(s.units,5)


class HoneypotTests(unittest.TestCase):
    def test_confirmed_attributes_and_perk_invariance(self):
        for perk in PERKS:
            e=scene(perks=(perk,)*4);h=honey(e);c=e.world.colonies[0]
            self.assertEqual((h.max_hp,h.hp,h.damage,movement(h,c),load(h,c),cost_half('honeypot',c)),(15,15,0,1,0,10))
        with self.assertRaises(ValueError):Ant(999,0,(1,1),kind='honeypot',stored_food=10.5)
    def test_exact_five_cost_one_action_and_reserve_floor(self):
        for funds,expected in ((14.5,0),(15,1)):
            e=scene(reproduction_enabled=True)
            for i in range(6):add(e,(10+i,10))
            c=e.world.colonies[0];c.upgraded=True;c.reserves=funds;before=e.food.accounting()['residual']
            e.reproduction.tick(1);e.reproduction.tick(1)
            hs=[a for a in e.world.ants if a.kind=='honeypot']
            self.assertEqual(len(hs),expected);self.assertEqual(c.reserves,funds-(5 if expected else 2))
            self.assertEqual(c.produced_honeypots,expected);self.assertEqual(c.spent_half,10 if expected else 4)
            self.assertEqual(e.food.accounting()['residual'],before)
    def test_no_discount_or_free_honeypot_from_bonus_queue(self):
        e=scene(reproduction_enabled=True,strategic_reserves_enabled=False)
        c=e.world.colonies[0];c.upgraded=True;c.bonus_queue=['honeypot'];c.reserves=4.5
        e.reproduction.tick(1);self.assertFalse(e.world.ants)
        c.reserves=5;e.reproduction.tick(2)
        self.assertEqual(e.world.ants[0].kind,'honeypot');self.assertEqual(c.reserves,0);self.assertEqual(c.spent_half,10)
    def test_exact_paid_production_for_all_eight_abilities(self):
        for perk in PERKS:
            e=scene(reproduction_enabled=True,perks=(perk,)*4)
            for i in range(6):add(e,(10+i,10))
            c=e.world.colonies[0];c.upgraded=True;c.reserves=15
            e.reproduction.tick(1)
            self.assertEqual(e.world.ants[-1].kind,'honeypot');self.assertEqual(c.reserves,10)
            self.assertEqual(c.spent_half,10);self.assertFalse(c.bonus_queue)
    def test_blocked_spawning_or_negative_balance_cannot_create_honeypot(self):
        from simulation.terrain import STONE
        for blocked,food in ((False,-1),(True,15)):
            e=scene(reproduction_enabled=True)
            for i in range(6):add(e,(10+i,10))
            c=e.world.colonies[0];c.upgraded=True;c.reserves=food
            if blocked:
                for p in e.navigation.home(0):e.world.terrain.set(*p,STONE)
            e.reproduction.tick(1)
            self.assertFalse(any(a.kind=='honeypot' for a in e.world.ants));self.assertEqual(c.reserves,food)
    def test_total_war_still_prioritizes_soldiers(self):
        e=scene(reproduction_enabled=True)
        for i in range(6):add(e,(10+i,10))
        c=e.world.colonies[0];c.upgraded=True;c.reserves=5;c.strategic_state='Total War'
        e.reproduction.tick(1);self.assertEqual(e.world.ants[-1].kind,'soldier');self.assertEqual(c.reserves,3)
    def test_no_harvesting_attacks_or_digging(self):
        e=scene(combat_enabled=True);h=honey(e);enemy=add(e,(26,25),1,'soldier');f=source(e)
        self.assertFalse(e.food.harvest(f,1,1,ant=h));self.assertFalse(e.construction.dig(h,(24,25),1))
        e.fsm.resolve_action(h,1);self.assertEqual(f.units,5);self.assertEqual(h.cargo,0)
        e.combat.resolve(1);self.assertEqual(h.hp,12);self.assertEqual(enemy.hp,12)
        self.assertEqual(e.combat.attacks,1);self.assertNotEqual(h.last_action,'attack')
    def test_capacity_partial_load_and_one_worker_action(self):
        e=scene();h=honey(e,units=9.5);a=add(e,(24,25));a.cargo=1;a.state='deliver-honeypot';a.honeypot_id=h.id
        e.honeypots.begin_plan();before=e.food.accounting()['residual']
        e.fsm.resolve_action(a,1);e.fsm.resolve_action(a,1)
        self.assertEqual((h.stored_food,a.cargo),(10,.5));self.assertEqual(e.food.accounting()['residual'],before)
    def test_enemy_and_distant_workers_cannot_load(self):
        e=scene();h=honey(e)
        for p,faction in (((24,25),1),((23,25),0)):
            a=add(e,p,faction);a.cargo=1;a.state='deliver-honeypot';a.honeypot_id=h.id
            e.honeypots.begin_plan();self.assertFalse(e.honeypots.action(a,1))
        self.assertEqual(h.stored_food,0)
    def test_autonomous_source_to_honeypot_delivery_and_soil_accounting(self):
        e=scene(exploration_enabled=False);h=honey(e);a=add(e,(23,25));f=source(e,(23,25),25,'large')
        before=e.food.accounting()['residual'];soil=e.construction.soil_total();e.food.rebuild_scent();e._plan()
        for _ in range(22):
            e.advance(1)
            self.assertEqual(e.food.accounting()['residual'],before)
            self.assertEqual(e.construction.soil_total(),soil)
            self.assertTrue(np.all(e.world.terrain.occupancy<=e.world.terrain.capacity))
        self.assertGreater(h.stored_food,0);self.assertLessEqual(h.stored_food,10);self.assertGreater(e.honeypots.loaded,0)
    def test_explicit_follow_hold_reposition_and_retreat_states(self):
        e=scene(combat_enabled=True);h=honey(e,(20,20));ally=add(e,(27,20))
        e.exploration.expedition_ids={ally.id};ally.exploration_target=(35,20)
        e.honeypots.begin_plan();e.combat.refresh();e.honeypots.prepare(h,e.combat);self.assertEqual(h.state,'honeypot-follow')
        e.exploration.expedition_ids.clear();e.honeypots.prepare(h,e.combat);self.assertEqual(h.state,'honeypot-reposition')
        place(e,ally,(21,20));h.escort_target=None;e.honeypots.begin_plan();e.honeypots.prepare(h,e.combat)
        self.assertEqual(h.state,'honeypot-hold')
        foe=add(e,(20,21),1,'soldier');e.combat.refresh();e.honeypots.prepare(h,e.combat)
        self.assertEqual(h.state,'honeypot-retreat');self.assertGreater(abs(h.target[0]-foe.position[0])+abs(h.target[1]-foe.position[1]),1)
    def test_stored_food_is_not_queen_money_or_healing(self):
        e=scene(reproduction_enabled=True);h=honey(e,units=10)
        for i in range(6):add(e,(10+i,10))
        c=e.world.colonies[0];c.upgraded=True;c.reserves=0;c.queen.hp=40
        e.reproduction.tick(1);e.economy.tick(1)
        self.assertEqual(len(e.world.ants),7);self.assertEqual(c.queen.hp,40)
        self.assertEqual(c.reserves,0);self.assertEqual(h.stored_food,10)
    def test_retreat_never_moves_closer_when_only_exit_is_unsafe(self):
        from simulation.terrain import STONE
        e=scene(combat_enabled=True);h=honey(e,(20,20));foe=add(e,(22,20),1,'soldier')
        for p in ((19,20),(20,19),(20,21)):e.world.terrain.set(*p,STONE)
        e.combat.refresh();e.honeypots.begin_plan();e.honeypots.prepare(h,e.combat)
        self.assertEqual(h.state,'honeypot-retreat');self.assertEqual(h.target,h.position)
    def test_ui_counts_storage_and_inspection_are_observational(self):
        import os
        os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
        import pygame
        from ui.renderer import Renderer
        from ui.food_economy import economy_lines
        from benchmarks.honeypots import fingerprint
        pygame.init()
        try:
            screen=pygame.display.set_mode((1000,800));e=scene();h=honey(e,units=4)
            r=Renderer(screen,e);before=fingerprint(e);r.draw(e)
            self.assertIn('Honeypots 1 | stored 4','\n'.join(economy_lines(e)))
            r.inspect(e,r.point(e,h.position));self.assertEqual(r.selected_id,h.id)
            r.draw(e);self.assertEqual(fingerprint(e),before)
        finally:pygame.quit()
    def test_queenless_hunger_healing_and_fixed_storage_after_perk_loss(self):
        e=scene(perks=('heavy-lifting',)*4);h=honey(e,units=10);c=e.world.colonies[0];c.queen.hp=0
        e.lifecycle.cleanup(0);self.assertEqual(h.stored_food,10)
        e.lifecycle.hunger(5);self.assertEqual(h.hp,14)
        before=e.food.accounting()['residual'];e.fsm.resolve_action(h,5)
        self.assertEqual(h.hp,15);self.assertEqual(h.stored_food,9);self.assertEqual(e.food.accounting()['residual'],before)


class DeathDropTests(unittest.TestCase):
    def test_full_partial_and_empty_inventory_exact_neutral_drop(self):
        for units in (10,3.5,0):
            e=scene();h=honey(e,units=units);before=e.food.accounting()['residual'];generated=e.food.generated_units
            h.hp=0;e.lifecycle.cleanup(1);e.lifecycle.cleanup(1)
            drops=[f for f in e.world.food if f.tier=='drop']
            self.assertEqual(sum(f.units for f in drops),units);self.assertEqual(h.stored_food,0)
            self.assertEqual(len(drops),1 if units else 0)
            if drops:self.assertEqual(drops[0].position,(25,25))
            self.assertEqual(e.food.generated_units,generated);self.assertEqual(e.food.accounting()['residual'],before)
    def test_fatal_combat_creates_exact_drop_and_clears_occupancy(self):
        e=scene(combat_enabled=True);h=honey(e,units=7);h.hp=3
        foe=add(e,(26,25),1,'soldier');before=e.food.accounting()['residual']
        e.combat.resolve(1);self.assertEqual(h.hp,0);self.assertEqual(foe.hp,12)
        e.lifecycle.cleanup(1)
        self.assertEqual(sum(f.units for f in e.world.food if f.tier=='drop'),7)
        self.assertEqual(e.world.terrain.occupancy[25,25],0)
        self.assertEqual(e.food.accounting()['residual'],before)
    def test_existing_source_not_overwritten_and_fallback_is_nearest(self):
        e=scene();f=source(e,units=5);h=honey(e,units=3);before=e.food.accounting()['residual']
        h.hp=0;e.lifecycle.cleanup(1);drop=next(f for f in e.world.food if f.tier=='drop')
        self.assertEqual((f.position,f.tier,f.units),((25,25),'small',5))
        self.assertEqual(drop.position,(24,25));self.assertEqual(e.food.accounting()['residual'],before)
    def test_enemy_collects_drop_and_physically_delivers_to_own_queen(self):
        e=scene();h=honey(e,units=1);h.hp=0;e.lifecycle.cleanup(1)
        enemy=add(e,(25,25),1);before=e.food.accounting()['residual'];e.fsm.resolve_action(enemy,2)
        self.assertEqual(enemy.cargo,1)
        place(e,enemy,e.fsm.base_cells(enemy)[0]);e.fsm.resolve_action(enemy,3)
        self.assertEqual(e.world.colonies[1].reserves,1);self.assertEqual(e.food.accounting()['residual'],before)
    def test_depleted_drop_does_not_respawn_or_create_greed_credit(self):
        e=scene(perks=('greed',)*4);h=honey(e,units=1);h.hp=0;e.lifecycle.cleanup(1)
        a=add(e,(25,25));e.fsm.resolve_action(a,2);drop=next(f for f in e.world.food if f.tier=='drop')
        self.assertIsNone(drop.respawn_deadline);self.assertFalse(e.world.colonies[0].greed_seen)
        e.food.tick(27);self.assertFalse(any(f.tier=='drop' for f in e.world.food));self.assertEqual(e.food.generated_units,0)
    def test_death_drop_reset_and_replay_consistency(self):
        from benchmarks.honeypots import fingerprint
        from simulation.engine import Engine
        a,b=scene(),scene()
        for e in (a,b):
            h=honey(e,units=3.5);source(e,units=5);h.hp=0;e.lifecycle.cleanup(1)
            add(e,(24,25),1);e.food.rebuild_scent();e._plan()
        for _ in range(8):
            a.advance(1);b.advance(.25);b.advance(.75)
            self.assertEqual(fingerprint(a),fingerprint(b))
        a.reset();self.assertFalse(a.food.pending_drops)
        self.assertEqual(fingerprint(a),fingerprint(Engine(a.config)))
    def test_depot_overlap_and_queued_placement_conserve_inventory(self):
        e=scene();d,a=build(e);h=honey(e,d.position,4);h.hp=0
        before=e.food.accounting()['residual'];e.lifecycle.cleanup(1)
        drop=next(f for f in e.world.food if f.tier=='drop')
        self.assertNotIn(drop.position,d.footprint);self.assertNotIn("units",asdict(d))
        self.assertEqual(e.food.accounting()['residual'],before)
        other=scene(drop_placement_budget=1);h=honey(other,(10,10),2)
        other.world.terrain.capacity[:]=0;before=other.food.accounting()['residual'];h.hp=0;other.lifecycle.cleanup(1)
        self.assertEqual(sum(j.units for j in other.food.pending_drops),2)
        other.world.terrain.set(12,10,0)
        for t in range(2,20):other.food.tick(t)
        self.assertEqual(sum(f.units for f in other.world.food if f.tier=='drop'),2)
        self.assertEqual(other.food.accounting()['residual'],before)


class ExplorationTests(unittest.TestCase):
    def test_limited_scouts_and_no_hidden_food_knowledge(self):
        a,b=scene(exploration_start_turn=0),scene(exploration_start_turn=0)
        for e in (a,b):
            for p in ((8,8),(9,8),(10,8),(11,8),(12,8),(13,8),(14,8),(15,8)):add(e,p)
        source(b,(50,50),25,'large')
        for e in (a,b):e.food.rebuild_scent();e._plan()
        self.assertEqual(a.exploration.roles,b.exploration.roles)
        self.assertLessEqual(len(a.exploration.roles),2)
        for left,right in zip(a.world.ants,b.world.ants):
            self.assertEqual((left.state,left.target,left.path),(right.state,right.target,right.path))
        self.assertTrue(any(x.state=='central-expedition' for x in a.world.ants))
        self.assertTrue(any(x.state=='frontier-explore' for x in a.world.ants))
    def test_expansion_beyond_corner_without_abandoning_all_harvesters(self):
        from simulation.engine import Engine
        e=Engine(Config(size=64,food_count=0,stone_density=0,large_stone_density=0,
                        reproduction_enabled=False,combat_enabled=False,exploration_start_turn=0))
        start=e.world.colonies[0].queen.position
        farthest=0
        for _ in range(60):
            e.advance(1)
            farthest=max(farthest,max(abs(a.position[0]-start[0])+abs(a.position[1]-start[1]) for a in e.world.ants if a.faction==0))
            self.assertLessEqual(sum(a.id in e.exploration.expedition_ids for a in e.world.ants if a.faction==0),1)
        self.assertGreater(farthest,24);self.assertGreater(len(e.exploration.seen[0]),2)
    def test_shared_exploration_routes_bound_field_count(self):
        e=scene(exploration_start_turn=0)
        for i in range(80):add(e,(10+i%20,10+i//20))
        e._plan()
        goals={a.target for a in e.world.ants if a.state in ('central-expedition','frontier-explore')}
        self.assertLessEqual(len(goals),2)
        self.assertLessEqual(len([k for k in e.navigation.fields if k[0]=='explore' and k[1]==0]),2)
    def test_scout_uses_actual_scent_without_learning_unknown_source_coordinates(self):
        from ai.pathfinding import distance
        e=scene(exploration_start_turn=0);add(e,(10,10));a=add(e,(18,18));f=source(e,(20,20),5)
        e.food.rebuild_scent();e._plan()
        self.assertNotIn(f.id,a.known_food)
        self.assertLess(distance(a.path[-1],f.position),distance(a.position,f.position))
    def test_defense_and_total_war_keep_existing_priorities(self):
        e=scene(exploration_start_turn=0)
        for i in range(8):add(e,(10+i,10))
        e.world.colonies[0].strategic_state='Total War';e.exploration.begin_plan()
        self.assertFalse(e.exploration.expedition_ids)
        e.world.colonies[0].strategic_state='Alert';e.world.colonies[0].threat='critical';e.exploration.begin_plan()
        self.assertFalse(e.exploration.expedition_ids)
    def test_replay_reset_and_food_soil_occupancy_invariants(self):
        from simulation.engine import Engine
        from benchmarks.honeypots import fingerprint
        a,b=scene(exploration_start_turn=0),scene(exploration_start_turn=0)
        for e in (a,b):
            h=honey(e,units=5);add(e,(23,25));add(e,(27,25));source(e,(23,25),25,'large');e.food.rebuild_scent();e._plan()
        offset=a.food.accounting()['residual'];soil=a.construction.soil_total()
        for _ in range(105):
            a.advance(1);b.paused=True;b.advance(10);b.paused=False;b.advance(.5);b.advance(.5)
            self.assertEqual(fingerprint(a),fingerprint(b));self.assertEqual(a.food.accounting()['residual'],offset)
            self.assertEqual(a.construction.soil_total(),soil);self.assertTrue(np.all(a.world.terrain.occupancy<=a.world.terrain.capacity))
        a.reset();self.assertEqual(fingerprint(a),fingerprint(Engine(a.config)))
