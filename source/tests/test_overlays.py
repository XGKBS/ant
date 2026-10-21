import gc
import math
import os
import unittest
import weakref
from types import MappingProxyType
import numpy as np
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import pygame
from config import Config, COLORS
from entities.models import Ant, Food
from simulation.engine import Engine
from simulation.terrain import PASSAGE
from ui.controls import Controls
from ui.renderer import Renderer
from ui.overlays import Overlays, InfluenceStyle, influence
from ai.pheromones import BASE, FOOD, BATTLE


def fixture(size=32):
    # Single-source/empty-field overlay assertions are intentionally isolated.
    e = Engine(Config(size=size, supply_stations_enabled=False, food_count=0, stone_density=0, large_stone_density=0,
                      reproduction_enabled=False, combat_enabled=False))
    e.world.ants.clear()
    e.world.terrain.occupancy[:] = 0
    return e


def put(e, position, faction=0, kind='worker'):
    a = Ant(e.world.allocate_id(), faction, position, kind=kind)
    a.path = [position]
    e.world.ants.append(a)
    e.world.terrain.occupancy[position[1], position[0]] += 1
    return a


class OverlayTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1200, 800))

    def tearDown(self):
        pygame.quit()

    def test_independent_keyboard_and_mouse_toggles_all_combinations(self):
        e = fixture()
        r, c = Renderer(self.screen, e), Controls()
        r.draw(e)
        for mask in range(8):
            for i, (name, key) in enumerate((('scent', pygame.K_s), ('pheromones', pygame.K_p), ('territory', pygame.K_c))):
                desired = bool(mask & (1 << i))
                if r.overlays.enabled[name] != desired:
                    c.handle(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=''), e, r)
            self.assertEqual(list(r.overlays.enabled.values()), [bool(mask & (1 << i)) for i in range(3)])
            r.draw(e)
        before = dict(r.overlays.enabled)
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r.menu_rects['scent'].center)
        c.handle(click, e, r)
        self.assertEqual(r.overlays.enabled['scent'], not before['scent'])
        self.assertEqual(r.overlays.enabled['pheromones'], before['pheromones'])
        self.assertEqual(r.overlays.enabled['territory'], before['territory'])

    def test_menu_collapse_filters_and_ant_inspection(self):
        e = fixture()
        a = put(e, (12, 12))
        r, c = Renderer(self.screen, e), Controls()
        r.draw(e)
        old_scent_rect = r.menu_rects['scent']
        for action in ('faction', 'channel', 'menu'):
            self.assertTrue(r.click_menu(r.menu_rects[action].center))
        self.assertEqual((r.overlays.faction, r.overlays.channel, r.overlays.menu_open), (0, 0, False))
        self.assertFalse(r.click_menu(old_scent_rect.center))
        r.draw(e)
        self.assertEqual(set(r.menu_rects), {'menu'})
        c.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode='s'), e, r)
        self.assertTrue(r.overlays.enabled['scent'])
        c.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r.point(e, a.position)), e, r)
        self.assertEqual(r.selected_id, a.id)

    def test_scent_matches_every_actual_value_and_cardinal_radius(self):
        e, o = fixture(), Overlays()
        source = Food(100, (15, 15), 'medium', 10, 8)
        e.world.food = [source]
        o.toggle('scent')
        for turn in range(9):
            if turn:
                e.food.tick(turn)
            e.turn = turn
            e.food.rebuild_scent()
            o.prepare(e)
            for y in range(32):
                for x in range(32):
                    actual = e.food.sample((x, y))
                    self.assertAlmostEqual(float(o.scent_values[y, x]), actual, places=6)
                    alpha = o.surfaces['scent'].get_at((x, y)).a
                    self.assertEqual(bool(alpha), actual > 0)
            self.assertGreater(o.scent_values[15, 15+turn], 0)
            if turn < 8:
                self.assertEqual(o.scent_values[15, 16+turn], 0)
        self.assertGreater(o.surfaces['scent'].get_at((16, 15)).a, o.surfaces['scent'].get_at((22, 15)).a)

    def test_scent_depletion_and_downgrade_regeneration(self):
        e, o = fixture(), Overlays()
        f = Food(100, (15, 15), 'small', 1, 4, age=4)
        e.world.food = [f]
        o.toggle('scent')
        e.food.rebuild_scent()
        o.prepare(e)
        self.assertGreater(o.scent_values[15, 18], 0)
        e.food.harvest(f, 1)
        e.turn = 1
        e.food.rebuild_scent()
        o.prepare(e)
        self.assertFalse(np.any(o.scent_values))
        e.turn = 26
        e.food.tick(26)
        e.food.rebuild_scent()
        o.prepare(e)
        self.assertEqual(f.tier, 'micro')
        self.assertEqual(o.scent_values[15, 15], 1)
        self.assertEqual(o.scent_values[15, 16], 0)

    def test_pheromone_intensity_decay_reinforcement_and_faction_filter(self):
        e, o = fixture(), Overlays()
        o.toggle('pheromones')
        e.pheromones.reinforce(0, BASE, (12, 12), 8)
        e.pheromones.reinforce(2, FOOD, (15, 15), 16)
        o.prepare(e)
        original = o.surfaces['pheromones'].get_at((12, 12))
        self.assertEqual(original[:3], COLORS[0])
        e.pheromones.decay()
        e.turn = 1
        o.prepare(e)
        self.assertLess(o.surfaces['pheromones'].get_at((12, 12)).a, original.a)
        o.faction = 2
        o.prepare(e)
        self.assertEqual(o.surfaces['pheromones'].get_at((12, 12)).a, 0)
        self.assertEqual(o.surfaces['pheromones'].get_at((15, 15))[:3], COLORS[2])
        old = o.surfaces['pheromones'].get_at((15, 15)).a
        e.pheromones.reinforce(2, FOOD, (15, 15), 20)
        e.turn = 2
        o.prepare(e)
        self.assertGreater(o.surfaces['pheromones'].get_at((15, 15)).a, old)

    def test_decayed_pheromone_cutoff_clears_overlay(self):
        e, o = fixture(), Overlays()
        e.pheromones.reinforce(0, BASE, (15, 15), 8)
        o.toggle('pheromones')
        o.prepare(e)
        for _ in range(300): e.pheromones.decay()
        e.turn = 300
        o.prepare(e)
        self.assertFalse(e.pheromones.active)
        self.assertEqual(o.surfaces['pheromones'].get_at((15, 15)).a, 0)

    def test_all_three_pheromone_channels_have_distinct_detail_slots(self):
        e, o = fixture(), Overlays()
        o.toggle('pheromones')
        for f in range(4):
            for c in range(3):
                e.pheromones.reinforce(f, c, (15, 15), 2+f+c)
        o.prepare(e, detail=True)
        for f in range(4):
            for c in range(3):
                pixel = o.detail.get_at((15*4+f, 15*3+c))
                self.assertEqual(pixel[:3], COLORS[f])
                self.assertGreater(pixel.a, 0)
        o.channel, o.faction = BATTLE, 1
        o.prepare(e, detail=True)
        for f in range(4):
            for c in range(3):
                self.assertEqual(o.detail.get_at((60+f, 45+c)).a > 0, f == 1 and c == BATTLE)

    def test_filter_cycles_and_territory_independence(self):
        e, o = fixture(), Overlays()
        for name in o.enabled: o.toggle(name)
        o.prepare(e)
        scores = o.territory_scores.copy()
        for _ in range(5): o.cycle_faction()
        for _ in range(4): o.cycle_channel()
        self.assertEqual((o.faction, o.channel), (None, None))
        o.faction, o.channel = 3, FOOD
        o.prepare(e)
        np.testing.assert_array_equal(scores, o.territory_scores)

    def test_neutral_contested_and_ant_movement(self):
        e = fixture()
        scores, owner = influence(e)
        self.assertEqual(owner[16, 16], -1)
        e.world.terrain.dig(15, 15)
        a = put(e, (15, 15), 0)
        b = put(e, (15, 15), 1)
        scores, owner = influence(e)
        self.assertEqual(owner[15, 15], -2)
        self.assertEqual(scores[0, 15, 15], 1)
        self.assertEqual(scores[1, 15, 15], 1)
        b.position = (24, 24)
        _, owner = influence(e)
        self.assertEqual(owner[15, 15], a.faction)
        self.assertEqual(owner[20, 20], -1)
        self.assertEqual(owner[22, 22], 1)

    def test_configurable_contested_and_neutral_thresholds(self):
        e = fixture()
        put(e, (15, 15), 0)
        put(e, (16, 15), 1)
        _, contested = influence(e, InfluenceStyle(queen_radius=0))
        _, strict = influence(e, InfluenceStyle(queen_radius=0, contested_ratio=.9))
        _, neutral = influence(e, InfluenceStyle(queen_radius=0, neutral_threshold=2))
        self.assertEqual(contested[15, 15], -2)
        self.assertEqual(strict[15, 15], 0)
        self.assertEqual(neutral[15, 15], -1)
        o = Overlays()
        o.toggle('territory')
        o.prepare(e)
        builds = o.builds['territory']
        o.style = InfluenceStyle(queen_radius=0, contested_ratio=.9)
        o.prepare(e)
        self.assertEqual(o.builds['territory'], builds+1)
        self.assertEqual(o.territory_owner[15, 15], 0)

    def test_territory_formula_activity_and_actual_pheromones(self):
        e = fixture()
        e.pheromones.reinforce(2, BATTLE, (16, 16), 10)
        scores, owner = influence(e)
        self.assertAlmostEqual(scores[2, 16, 16], .2*10.25, places=6)
        self.assertEqual(owner[16, 16], 2)
        old = scores[0, 5, 5]
        e.world.colonies[0].received_half = 20
        e.world.colonies[0].produced_workers = 10
        new, _ = influence(e)
        self.assertAlmostEqual(new[0, 5, 5]/old, 1.5, places=6)

    def test_queen_death_removes_queen_term_but_survivors_keep_influence(self):
        e = fixture()
        put(e, (15, 15), 0)
        e.pheromones.reinforce(0, FOOD, (16, 15), 8)
        old, _ = influence(e)
        self.assertGreater(old[0, 5, 5], 0)
        e.world.colonies[0].queen.hp = 0
        e.lifecycle.cleanup(1)
        new, _ = influence(e)
        self.assertEqual(new[0, 5, 5], 0)
        self.assertGreater(new[0, 15, 15], 0)
        self.assertGreater(new[0, 15, 16], 0)
        for perk in ('heavy-lifting', 'sensitivity', 'speed'):
            e.world.colonies[0].perk = perk
            actual, _ = influence(e)
            np.testing.assert_array_equal(actual, new)

    def test_dig_fill_and_stone_updates_actual_fields(self):
        e, o = fixture(), Overlays()
        e.world.food = [Food(100, (8, 10), 'medium', 10, 8, age=8)]
        stone = e.construction.stones.register([(10, 10)], 4)
        e.pheromones.reinforce(0, FOOD, (11, 10), 8)
        for name in o.enabled: o.toggle(name)
        e.food.rebuild_scent()
        o.prepare(e)
        self.assertEqual(o.scent_values[10, 10], 0)
        self.assertTrue(e.world.terrain.dig(9, 10))
        e.food.rebuild_scent()
        o.prepare(e)
        self.assertAlmostEqual(o.scent_values[10, 9], e.food.sample((9, 10)))
        self.assertTrue(e.world.terrain.fill((9, 10)))
        e.food.rebuild_scent()
        o.prepare(e)
        self.assertTrue(e.construction.stones.move(stone, (1, 0)))
        e.food.rebuild_scent()
        o.prepare(e)
        self.assertGreater(o.scent_values[10, 10], 0)
        self.assertEqual(o.scent_values[10, 11], 0)
        self.assertEqual(o.territory_owner[10, 11], -1)
        # Actual historical chemicals can remain on newly blocked cells; display
        # them as the model stores them, rather than inventing extra decay.
        self.assertGreater(o.surfaces['pheromones'].get_at((11, 10)).a, 0)

    def test_camera_zoom_pan_viewport_alignment_and_clip(self):
        e = fixture()
        e.world.food = [Food(100, (12, 12), 'small', 5, 4, age=4)]
        e.construction.stones.register([(13, 12)], 4)
        e.food.rebuild_scent()
        r = Renderer(self.screen, e)
        r.overlays.toggle('scent')
        for zoom in (1, 2, 8):
            r.overview()
            r.zoom = zoom
            viewport, scale, origin = r.geometry(e)
            r.offset = [viewport.w/2-(origin[0]+12.5*scale)+.37, viewport.h/2-(origin[1]+12.5*scale)+.21]
            viewport, scale, origin = r.geometry(e)
            bounds = (max(0, math.floor(-origin[0]/scale)), max(0, math.floor(-origin[1]/scale)),
                      min(32, math.ceil((viewport.w-origin[0])/scale)), min(32, math.ceil((viewport.h-origin[1])/scale)))
            self.screen.fill((0, 0, 0))
            self.screen.set_clip(viewport)
            r.overlays.draw(self.screen, e, scale, origin, bounds)
            self.screen.set_clip(None)
            self.assertGreater(self.screen.get_at(r.point(e, (12, 13))).b, 0)
            self.assertEqual(self.screen.get_at(r.point(e, (13, 12)))[:3], (0, 0, 0))
            self.assertEqual(self.screen.get_at((900, 400))[:3], (0, 0, 0))

    def test_repeated_frames_do_not_rebuild_or_retain_multiple_viewports(self):
        e = fixture()
        r = Renderer(self.screen, e)
        for name in r.overlays.enabled: r.overlays.toggle(name)
        r.draw(e)
        builds = dict(r.overlays.builds)
        ids = [id(v[1]) for v in r.overlays.viewport_cache.values()]
        for _ in range(12):
            e.progress = .5
            r.draw(e)
        self.assertEqual(builds, r.overlays.builds)
        self.assertEqual(ids, [id(v[1]) for v in r.overlays.viewport_cache.values()])
        e.advance(.5)
        r.draw(e)
        self.assertEqual(r.overlays.builds, {name: n+1 for name, n in builds.items()})
        self.assertEqual(len(r.overlays.viewport_cache), 3)

    def test_detail_viewport_samples_world_coordinates_after_pan(self):
        e = fixture(512)
        e.pheromones.reinforce(2, BATTLE, (12, 12), 12)
        r = Renderer(self.screen, e, startup_focus=0)
        r.overlays.toggle('pheromones')
        for pan in (0, -45, 35):
            r.offset[0] += pan
            r.draw(e)
            x, y = r.overlays.detail_origin
            self.assertLess(r.overlays.detail.get_width(), 4*80)
            self.assertLess(r.overlays.detail.get_height(), 3*80)
            pixel = r.overlays.detail.get_at(((12-x)*4+2, (12-y)*3+BATTLE))
            self.assertEqual(pixel[:3], COLORS[2])
            self.assertGreater(pixel.a, 0)

    def test_pause_reset_end_and_preferences(self):
        e = fixture()
        r, c = Renderer(self.screen, e), Controls()
        for name in r.overlays.enabled: r.overlays.toggle(name)
        r.overlays.faction = 2
        e.paused = True
        r.draw(e)
        builds = dict(r.overlays.builds)
        e.advance(10)
        r.draw(e)
        self.assertEqual(r.overlays.builds, builds)
        e.end()
        r.draw(e)
        self.assertEqual(r.overlays.builds, builds)
        old = weakref.ref(e.world)
        c.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r, unicode='r'), e, r)
        r.draw(e)
        gc.collect()
        self.assertIsNone(old())
        self.assertFalse(e.ended)
        self.assertTrue(all(r.overlays.enabled.values()))
        self.assertEqual(r.overlays.faction, 2)
        self.assertIs(r.overlays.world, e.world)

    def test_end_screen_filters_do_not_change_final_statistics(self):
        from benchmarks.phase4b import full_fingerprint
        e = fixture()
        e.end('Final statistics retained')
        old = full_fingerprint(e)
        r, c = Renderer(self.screen, e), Controls()
        for key in (pygame.K_s, pygame.K_p, pygame.K_c, pygame.K_g, pygame.K_h):
            c.handle(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=''), e, r)
            r.draw(e)
        self.assertEqual(full_fingerprint(e), old)

    def test_read_only_arrays_and_scent_mapping(self):
        e = fixture()
        e.food.scent = MappingProxyType({(12, 12): .75})
        for a in (e.pheromones.values, e.world.terrain.capacity, e.world.terrain.cells):
            a.flags.writeable = False
        r = Renderer(self.screen, e)
        for name in r.overlays.enabled: r.overlays.toggle(name)
        r.draw(e)
        self.assertAlmostEqual(r.overlays.scent_values[12, 12], .75)

    def test_enabled_vs_disabled_complete_simulation_equivalence(self):
        from benchmarks.phase4b import full_fingerprint
        config = Config(size=32, seed=47, food_count=8, perks=('heavy-lifting', 'speed', 'blitz', 'sensitivity'))
        a, b = Engine(config), Engine(config)
        r, c = Renderer(self.screen, b), Controls()
        for name in r.overlays.enabled: r.overlays.toggle(name)
        for turn in range(30):
            r.overlays.cycle_faction()
            r.overlays.cycle_channel()
            r.zoom = 1+(turn % 4)
            r.draw(b)
            r.draw(b)
            self.assertEqual(full_fingerprint(a), full_fingerprint(b))
            a.advance(1)
            b.advance(1)
        a.end()
        b.end()
        r.draw(b)
        self.assertEqual(full_fingerprint(a), full_fingerprint(b))

    def test_default_map_memory_and_cache_bound_across_camera_changes(self):
        e = fixture(512)
        r = Renderer(self.screen, e)
        for name in r.overlays.enabled: r.overlays.toggle(name)
        r.draw(e)
        self.assertLess(r.overlays.cache_bytes(), 32*1024**2)
        for zoom in (2, 4, 8, 16, 1):
            r.zoom = zoom
            r.draw(e)
            self.assertLess(r.overlays.cache_bytes(), 48*1024**2)
            self.assertEqual(len(r.overlays.viewport_cache), 3)

if __name__ == '__main__':
    unittest.main()
