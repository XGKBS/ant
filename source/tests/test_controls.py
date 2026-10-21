import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import unittest
import pygame
from config import Config
from simulation.engine import Engine
from ui.controls import Controls
from ui.renderer import Renderer

class ControlsTests(unittest.TestCase):
    def test_inspection_focus_and_view_do_not_change_simulation(self):
        pygame.init()
        try:
            engine = Engine(Config())
            renderer = Renderer(pygame.display.set_mode((1200, 800)), engine, startup_focus=0)
            controls = Controls()
            self.assertEqual(renderer.zoom, 8)
            ant = engine.world.ants[0]
            point = renderer.point(engine, engine.display_position(ant))
            rng = engine.world.rng.getstate()
            state = [(a.position, list(a.path), a.state, a.cargo) for a in engine.world.ants]
            controls.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point), engine, renderer)
            self.assertIsNotNone(renderer.selected_id)
            renderer.draw(engine)
            controls.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_HOME, unicode=''), engine, renderer)
            self.assertEqual(renderer.zoom, 1)
            controls.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, unicode=''), engine, renderer)
            self.assertEqual(renderer.focus_faction, 1)
            renderer.zoom = 16
            renderer.draw(engine, '300')
            self.assertEqual(state, [(a.position, list(a.path), a.state, a.cargo) for a in engine.world.ants])
            self.assertEqual(rng, engine.world.rng.getstate())
            self.assertEqual(engine.turn, 0)
        finally:
            pygame.quit()

    def test_runtime_controls_and_render(self):
        pygame.init()
        try:
            engine = Engine(Config(size=32))
            renderer = Renderer(pygame.display.set_mode((1200, 800)), engine)
            controls = Controls()
            def key(k, text=''):
                return controls.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=text), engine, renderer)
            key(pygame.K_4)
            self.assertEqual(engine.speed, 8)
            key(pygame.K_SPACE)
            engine.advance(1)
            self.assertEqual(engine.turn, 0)
            key(pygame.K_t)
            key(pygame.K_5, '5')
            renderer.draw(engine, controls.cap_text)
            key(pygame.K_RETURN)
            self.assertEqual(engine.max_turns, 5)
            self.assertTrue(engine.paused)
            key(pygame.K_SPACE)
            engine.advance(1)
            self.assertEqual(engine.turn, 5)
            self.assertTrue(engine.ended)
            renderer.draw(engine)
            key(pygame.K_r)
            self.assertFalse(engine.ended)
            self.assertEqual(engine.max_turns, None)
            key(pygame.K_t)
            key(pygame.K_0, '0')
            key(pygame.K_RETURN)
            self.assertIsNotNone(controls.cap_text)
            key(pygame.K_ESCAPE)
            key(pygame.K_e)
            self.assertTrue(engine.ended)
            self.assertFalse(controls.handle(pygame.event.Event(pygame.QUIT), engine, renderer))
        finally:
            pygame.quit()
