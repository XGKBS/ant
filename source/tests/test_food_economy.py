"""Approved Phase 4E mechanics and default-enabled integration regressions."""
import os,unittest
from dataclasses import replace,asdict
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import pygame
import numpy as np
from config import Config
from simulation.engine import Engine
from entities.models import Ant,Food
from systems.economy import food_upkeep
from systems.supply import OFFSETS,create_stations
from simulation.terrain import STONE
from ui.application import Application
from ui.renderer import Renderer
from ui.food_economy import economy_lines
from tests.test_resources import replan

def quiet(**kw):
    options=dict(size=64,food_count=0,stone_density=0,large_stone_density=0,reproduction_enabled=False,combat_enabled=False,construction_enabled=False)
    options.update(kw)
    return Engine(Config(**options))

def population(e,n,faction=0):
    e.world.ants=[Ant(e.world.allocate_id(),faction,(15+i%30,15+i//30)) for i in range(n)]
    return e.world.colonies[faction]

class UpkeepTests(unittest.TestCase):
    def test_all_reference_and_boundary_values(self):
        values={0:0,1:1,25:25,49:49,50:50,51:52,75:100,99:148,100:150,101:153,107:171,150:300,151:304,200:500,250:750,300:1050,1000:10500}
        for n,expected in values.items():
            with self.subTest(n=n):self.assertEqual(food_upkeep(n),expected)
        with self.assertRaises(ValueError):food_upkeep(-1)
    def test_marginal_rate_and_unbounded_integer_formula(self):
        for n in range(1,2000):self.assertEqual(food_upkeep(n)-food_upkeep(n-1),(n-1)//50+1)
        n=10**30;q,r=divmod(n,50)
        self.assertEqual(food_upkeep(n),25*q*(q+1)+r*(q+1))
    def test_schedule_exact_population_signed_and_idempotent(self):
        e=quiet();c=population(e,107);c.reserves=30
        for turn in range(1,100):e.economy.tick(turn)
        self.assertEqual(c.reserves,30)
        e.economy.tick(100);e.economy.tick(100)
        self.assertEqual(c.reserves,-141)
        e.economy.tick(101);self.assertEqual(c.reserves,-141)
        e.world.ants[0].hp=0;e.world.ants.pop();e.world.ants[1].kind='soldier'
        e.economy.tick(200)
        self.assertEqual(c.reserves,-141-food_upkeep(105))
        self.assertEqual(c.upkeep_spent_half,2*(171+food_upkeep(105)))
    def test_birth_at_boundary_is_included_and_queen_excluded(self):
        e=quiet(reproduction_enabled=True,strategic_reserves_enabled=False);e.world.ants.clear();e.world.terrain.occupancy[:]=0
        c=e.world.colonies[0];c.reserves=2
        e.turn=99;e._plan();e.advance(1)
        self.assertEqual(len(e.world.ants),1);self.assertEqual(c.last_upkeep,1);self.assertEqual(c.reserves,-1)
    def test_colonies_settle_independently_including_queenless_survivors(self):
        e=quiet();e.world.colonies[1].queen.hp=0;e.lifecycle.cleanup(0)
        e.economy.tick(100)
        self.assertEqual([c.last_upkeep for c in e.world.colonies],[2]*4)
        self.assertEqual(e.world.colonies[1].queen.hp,0)
    def test_no_ordinary_ants_zero_upkeep(self):
        e=quiet();e.world.ants=[];e.economy.tick(100)
        self.assertEqual([c.reserves for c in e.world.colonies],[0]*4)

class SurvivalTests(unittest.TestCase):
    def test_negative_damage_two_turns_and_recovery_reset(self):
        e=quiet();c=e.world.colonies[0];c.reserves=-.5
        for turn in range(1,7):
            e.economy.tick(turn);self.assertEqual(c.queen.hp,50-turn//2)
        for food in (0,3):
            c.reserves=food;e.economy.tick(c.last_economy_turn+1)
            self.assertEqual(c.starvation_turns,0)
            hp=c.queen.hp;c.reserves=-1
            e.economy.tick(c.last_economy_turn+1);self.assertEqual(c.queen.hp,hp)
            e.economy.tick(c.last_economy_turn+1);self.assertEqual(c.queen.hp,hp-1)
    def test_positive_and_zero_never_accumulate_starvation(self):
        for food in (0,.5,10):
            e=quiet();c=e.world.colonies[0];c.reserves=food
            for turn in range(1,20):e.economy.tick(turn)
            self.assertEqual(c.starvation_turns,0);self.assertEqual(c.queen.hp,50)
    def test_healing_examples_fractional_and_one_processing_per_turn(self):
        for missing,food,healed in ((10,20,2),(1,20,1),(10,1,1),(10,0,0),(10,-15,0),(0,100,0),(10,.5,.5)):
            e=quiet();c=e.world.colonies[0];c.queen.hp=c.queen.max_hp-missing;c.reserves=food
            e.economy.tick(1);e.economy.tick(1)
            self.assertEqual(c.last_healing,healed);self.assertEqual(c.reserves,food-healed)
            self.assertEqual(c.queen.hp,50-missing+healed)
            self.assertEqual(c.healing_spent_half,2*healed)
    def test_canonical_maximum_hp_not_current_wounded_hp(self):
        e=quiet();q=e.world.colonies[0].queen;q.hp=49.5
        c=e.world.colonies[0];c.reserves=100;e.economy.tick(1)
        self.assertEqual(q.hp,q.max_hp);self.assertEqual(c.reserves,99.5)
    def test_dead_queen_no_healing_and_existing_trophy_victory(self):
        e=quiet();e.world.ants=[];e.world.terrain.occupancy[:]=0
        for c in e.world.colonies[:3]:c.queen.hp=1;c.reserves=-10
        e._plan();e.advance(2)
        self.assertTrue(e.ended);self.assertEqual(e.winner,3)
        self.assertEqual(e.food.trophy_created,150)
        for c in e.world.colonies[:3]:
            self.assertEqual(c.queen.hp,0);self.assertIsNotNone(c.death_turn)
            c.reserves=100
        e.economy.tick(3)
        self.assertTrue(all(c.queen.hp==0 for c in e.world.colonies[:3]))
    def test_simultaneous_starvation_no_winner(self):
        e=quiet();e.world.ants=[];e.world.terrain.occupancy[:]=0
        for c in e.world.colonies:c.queen.hp=1;c.reserves=-1
        e.advance(2);self.assertTrue(e.ended);self.assertIsNone(e.winner)
        self.assertEqual(e.food.trophy_created,200)
    def test_delivery_repays_debt_without_clamp(self):
        e=quiet();a=e.world.ants[0];c=e.world.colonies[0]
        a.position=e.fsm.base_cells(a)[0];a.cargo=1.5;c.reserves=-1
        e.fsm.resolve_action(a,1)
        self.assertEqual(c.reserves,.5);self.assertEqual(a.cargo,0)
        self.assertEqual(c.received_half,3)
    def test_debt_blocks_paid_and_free_births_and_upgrades(self):
        e=quiet(reproduction_enabled=True);c=e.world.colonies[0]
        c.reserves=-.5;c.upgraded=True;c.bonus_queue=['worker'];n=len(e.world.ants)
        e.reproduction.tick(1)
        self.assertEqual(len(e.world.ants),n);self.assertEqual(c.reserves,-.5)
        c.upgraded=False;e.reproduction.tick(2)
        self.assertFalse(c.upgraded)
    def test_upkeep_precedes_healing_and_start_of_starvation(self):
        e=quiet();c=e.world.colonies[0];c.queen.hp=40;c.reserves=1
        e.economy.tick(100)
        self.assertEqual(c.reserves,-1);self.assertEqual(c.last_healing,0);self.assertEqual(c.starvation_turns,1)
        e.economy.tick(101);self.assertEqual(c.queen.hp,39)
    def test_delivery_at_turn_end_stops_imminent_starvation(self):
        e=quiet();a=e.world.ants[0];e.world.ants=[a]
        c=e.world.colonies[0];c.reserves=-1;c.starvation_turns=1
        a.position=e.fsm.base_cells(a)[0];a.path=[a.position];a.cargo=1
        e.world.terrain.occupancy[:]=0;e.world.terrain.occupancy[a.position[1],a.position[0]]=1
        e.turn=25;e.advance(1)
        self.assertEqual(c.reserves,0);self.assertEqual(c.starvation_turns,0);self.assertEqual(c.queen.hp,50)
    def test_nonlethal_combat_precedes_food_based_healing(self):
        e=quiet(combat_enabled=True);e.world.ants=[];e.world.terrain.occupancy[:]=0
        c=e.world.colonies[0];c.reserves=5
        a=Ant(e.world.allocate_id(),1,(1,2),kind='soldier');a.path=[a.position]
        e.world.ants=[a];e.world.terrain.occupancy[2,1]=1;e.advance(1)
        self.assertEqual(c.queen.hp,49);self.assertEqual(c.last_healing,2);self.assertEqual(c.reserves,3)
    def test_combat_death_cannot_be_undone_by_healing(self):
        e=quiet(combat_enabled=True);e.world.ants=[];e.world.terrain.occupancy[:]=0
        c=e.world.colonies[0];c.queen.hp=1;c.reserves=10
        a=Ant(e.world.allocate_id(),1,(1,2),kind='soldier');a.path=[a.position]
        e.world.ants=[a];e.world.terrain.occupancy[2,1]=1;e.advance(1)
        self.assertEqual(c.queen.hp,0);self.assertEqual(c.last_healing,0);self.assertIsNotNone(c.death_turn)

class SupplyTests(unittest.TestCase):
    def test_exact_mirrored_offsets_all_map_sizes_and_no_terrain_changes(self):
        for size in (64,128,256,512):
            e=quiet(size=size);w=e.world
            self.assertEqual(len(w.stations),12);self.assertEqual(len(set(w.station_locations)),12)
            for c in w.colonies:
                stations=[s for s in w.stations if s.origin_faction==c.faction]
                expected=[(c.queen.position[0]+dx,c.queen.position[1]+dy) for dx,dy in OFFSETS[c.faction]]
                self.assertEqual([s.position for s in stations],expected)
                for s in stations:self.assertTrue(w.terrain.capacity[s.position[1],s.position[0]])
            other=Engine(replace(e.config,supply_stations_enabled=False))
            np.testing.assert_array_equal(w.terrain.cells,other.world.terrain.cells)
            from simulation.world import World
            self.assertEqual(World(e.config).rng.getstate(),World(replace(e.config,supply_stations_enabled=False)).rng.getstate())
    def test_deterministic_nearest_valid_fallback_and_reason(self):
        e=quiet();w=e.world;w.terrain.set(7,2,STONE)
        before=w.terrain.cells.copy();a=create_stations(w);b=create_stations(w)
        self.assertEqual([s.position for s in a],[s.position for s in b])
        self.assertNotEqual(a[0].position,(7,2));self.assertNotEqual(a[0].placement_reason,'exact offset')
        np.testing.assert_array_equal(before,w.terrain.cells)
    def test_initial_allocation_refill_idempotence_accumulation_permanence(self):
        e=quiet();identities=[(s.id,s.position) for s in e.world.stations]
        self.assertEqual(sum(s.units for s in e.world.stations),60)
        e.supply.tick(24);self.assertEqual(e.supply.generated_units,0)
        e.supply.tick(25);e.supply.tick(25)
        self.assertEqual(sum(s.units for s in e.world.stations),120)
        e.supply.tick(50);self.assertEqual(e.supply.generated_units,120)
        self.assertEqual([(s.id,s.position) for s in e.world.stations],identities)
    def test_partial_and_simultaneous_pickup_depletion_and_refill(self):
        e=quiet();s=e.world.stations[0];s.units=2.5
        a=e.world.ants[0];a.position=s.position
        for amount in (1.5,1.5,1):
            got=e.food.harvest(s,1,amount,ant=a)
            if amount==1:self.assertFalse(got)
        self.assertEqual(s.units,0);self.assertEqual(s.collected_units,2.5);self.assertIsNone(s.respawn_deadline)
        e.food.tick(24);self.assertEqual(s.units,0)
        e.supply.tick(25);self.assertEqual(s.units,5);self.assertEqual(s.tier,'supply')
    def test_shared_passage_pickups_respect_load_and_one_action(self):
        e=quiet(perks=('heavy-lifting',)*4);s=e.world.stations[0];s.units=2.5
        ants=e.world.ants[:2];e.world.ants=ants;e.world.terrain.occupancy[:]=0
        e.world.terrain.dig(*s.position)
        for ant in ants:
            ant.position=s.position;ant.path=[s.position]
            e.world.terrain.occupancy[s.position[1],s.position[0]]+=1
        before=e.food.accounting()['inventory']
        for ant in ants:e.fsm.resolve_action(ant,1);e.fsm.resolve_action(ant,1)
        self.assertEqual([a.cargo for a in ants],[1.5,1])
        self.assertEqual(s.units,0);self.assertEqual(s.collected_units,2.5)
        self.assertEqual(e.food.accounting()['inventory'],before)
        self.assertTrue(all(a.action_used and a.last_action_turn==1 for a in ants))
    def test_workers_physically_collect_and_deliver_to_own_queen(self):
        e=quiet(perks=('heavy-lifting',)*4)
        for _ in range(24):e.advance(1)
        self.assertGreater(e.food.delivered,0)
        self.assertTrue(all(c.reserves>0 for c in e.world.colonies))
        self.assertGreater(sum(s.collected_units for s in e.world.stations),0)
        self.assertTrue(all(a.cargo<=1.5 for a in e.world.ants))
        self.assertEqual(e.food.accounting()['residual'],0)
    def test_public_coordinates_not_hidden_stock(self):
        a,b=quiet(),quiet();ant1=a.world.ants[0];ant2=b.world.ants[0]
        for s in b.world.stations:s.units=0
        a.fsm.public_station(ant1);b.fsm.public_station(ant2)
        self.assertEqual(ant1.target,ant2.target)
        self.assertEqual(len(a.world.station_locations),12)
        s=a.world.stations[0];s.units=0;ant1.position=s.position
        a.fsm.observe(ant1);a.fsm.public_station(ant1)
        self.assertNotEqual(ant1.target,s.position)
    def test_enemy_pickup_and_queenless_soldier_direct_eating(self):
        e=quiet();s=e.world.stations[0]
        a=e.world.ants[2];a.position=s.position;e.fsm.resolve_action(a,1)
        self.assertEqual(a.cargo,1);self.assertEqual(a.faction,1)
        c=e.world.colonies[1];c.queen.hp=0;e.lifecycle.cleanup(1)
        a.kind='soldier';a.cargo=0;a.hp=10;a.action_used=False;a.last_action=None
        before=s.units;e.fsm.resolve_action(a,2)
        self.assertEqual(a.hp,11);self.assertEqual(s.units,before-1);self.assertEqual(a.cargo,0)
    def test_greed_does_not_gain_ordinary_tier_tokens_from_stations(self):
        e=quiet(perks=('greed',)*4);a=e.world.ants[0]
        for s in e.world.stations:e.food.harvest(s,1,1,ant=a)
        self.assertFalse(e.world.colonies[0].greed_credits)
    def test_station_sites_protected_like_other_food_from_stone_coverage(self):
        e=quiet();s=e.world.stations[0];stone=e.construction.stones.register([(s.position[0]+1,s.position[1])],4)
        self.assertFalse(e.construction.stones.can_move(stone,(-1,0)))
    def test_full_food_soil_accounting_through_refills_upkeep_and_reproduction(self):
        e=quiet(reproduction_enabled=True,combat_enabled=True,construction_enabled=True)
        total=e.construction.soil_total()
        for _ in range(105):
            e.advance(1)
            self.assertEqual(e.food.accounting()['residual'],0)
            self.assertEqual(e.construction.soil_total(),total)
            self.assertTrue(np.all(e.world.terrain.occupancy<=e.world.terrain.capacity))
        self.assertEqual(e.supply.generated_units,240)
    def test_soldier_can_construct_despite_observing_public_food(self):
        e=quiet(construction_enabled=True);e.world.ants=[];e.world.terrain.occupancy[:]=0
        a=Ant(e.world.allocate_id(),0,(6,5),kind='soldier');a.path=[a.position]
        e.world.ants=[a];e.world.terrain.occupancy[5,6]=1
        self.assertTrue(e.construction.dig(a,(7,5),0));e._plan()
        self.assertTrue(a.known_food)
        for _ in range(8):e.advance(1)
        self.assertGreater(e.construction.completed['fill'],0)

class EconomyUITests(unittest.TestCase):
    def setUp(self):pygame.init();self.screen=pygame.display.set_mode((800,600),pygame.RESIZABLE)
    def tearDown(self):pygame.quit()
    def test_diagnostics_signed_debt_starvation_healing_countdowns(self):
        e=quiet();c=e.world.colonies[0];c.reserves=-20;e.economy.tick(1);e.turn=1
        text='\n'.join(economy_lines(e))
        for label in ('reserve -20','Debt 20','Starvation ACTIVE | next 1 turns','Upkeep 2/100 | next 99 turns','PUBLIC SUPPLY STATIONS: 12','At stations 60'):
            self.assertIn(label,text)
        c.reserves=3;c.queen.hp=40;e.economy.tick(2)
        self.assertIn('Last healing +2 HP | food 2','\n'.join(economy_lines(e)))
    def test_station_selection_alignment_zoom_pan_and_ant_priority(self):
        from ui import camera
        e=quiet();r=Renderer(self.screen,e);r.draw(e);s=e.world.stations[0]
        camera.zoom_at(r,e,4,r.point(e,s.position));camera.pan(r,e,(-5,-5));r.draw(e)
        r.inspect(e,r.point(e,s.position));self.assertEqual(r.selected_station,s.id)
        a=e.world.ants[0];a.position=s.position;a.path=[a.position]
        r.inspect(e,r.point(e,s.position));self.assertEqual(r.selected_id,a.id);self.assertIsNone(r.selected_station)
    def test_pause_menus_end_restart_and_economy_toggle_are_read_only(self):
        from benchmarks.phase4e import fingerprint
        app=Application(self.screen,Config(size=64),auto_start=True);app.draw()
        app.renderer.click_menu(app.renderer.economy_rect.center);self.assertTrue(app.renderer.economy_open)
        app.action('pause');before=fingerprint(app.engine)
        for _ in range(3):app.frame(200,[]);app.draw()
        self.assertEqual(before,fingerprint(app.engine))
        app.action('settings');app.frame(200,[]);self.assertEqual(before,fingerprint(app.engine))
        app.action('back_settings');app.action('end');before=fingerprint(app.engine);app.frame(200,[])
        self.assertEqual(before,fingerprint(app.engine))
        app.action('restart');self.assertEqual(len(app.engine.world.stations),12);self.assertEqual(app.engine.supply.generated_units,0)
        self.assertTrue(all(s.units==5 and s.next_refill==25 for s in app.engine.world.stations))
    def test_deterministic_replay_overlays_pause_restart_and_new_checkpoints(self):
        from benchmarks.phase4e import fingerprint
        a,b=quiet(),quiet();r=Renderer(self.screen,b)
        for name in r.overlays.enabled:r.overlays.enabled[name]=True
        hashes=[]
        for turn in range(55):
            a.advance(1);b.paused=True;b.advance(100);b.paused=False;b.advance(1);r.draw(b)
            self.assertEqual(fingerprint(a),fingerprint(b));hashes.append(fingerprint(a))
        a.reset()
        for expected in hashes:a.advance(1);self.assertEqual(expected,fingerprint(a))
if __name__=='__main__':unittest.main()

