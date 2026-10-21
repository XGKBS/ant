import gc
import os
import unittest
import weakref
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import pygame
from config import Config, PERKS
from ui.application import Application
from ui import camera
from benchmarks.phase4b import full_fingerprint

def key(code, text='', **kwargs):
    return pygame.event.Event(pygame.KEYDOWN, key=code, unicode=text, **kwargs)

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1200,800),pygame.RESIZABLE)
        self.app = Application(self.screen,Config(size=64))
        self.app.draw()

    def tearDown(self):
        pygame.quit()

    def event(self,event,elapsed=0):
        self.app.frame(elapsed,[event])
        self.app.draw()

    def click(self,name,field=False):
        collection = self.app.fields if field else self.app.buttons
        rect=collection[name]
        self.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=rect.center))

    def start(self):
        self.click('new')
        self.click('start')

    def test_startup_menu_does_not_initialize_or_advance(self):
        self.app.frame(120,[])
        self.assertIsNone(self.app.engine)
        self.assertEqual(set(self.app.buttons),{'new','settings','quit'})
        self.click('settings')
        self.app.frame(120,[])
        self.assertIsNone(self.app.engine)
        self.click('back_settings')
        self.assertEqual(self.app.mode,'main')

    def test_setup_all_map_sizes_and_independent_duplicate_abilities(self):
        self.click('new')
        for size in (64,128,256,512):
            self.click('size_'+str(size))
            self.assertEqual(self.app.draft_size,size)
        for faction in range(4):
            self.click('faction_'+str(faction))
            for perk in PERKS:
                self.click('perk_'+perk)
                self.assertEqual(self.app.draft_perks[faction],perk)
            self.click('perk_heavy-lifting')
        self.click('size_64')
        self.click('start')
        self.assertEqual(self.app.engine.config.perks,('heavy-lifting',)*4)
        self.assertEqual(self.app.engine.world.terrain.cells.shape,(64,64))
        self.assertEqual([c.active_perk for c in self.app.engine.world.colonies],['heavy-lifting']*4)

    def test_actual_initialization_at_each_supported_size(self):
        for size in (64,128,256,512):
            self.app.start(Config(size=size))
            self.app.draw()
            e=self.app.engine
            self.assertEqual(len(e.world.food),24)
            self.assertEqual(len(e.world.colonies),4)
            self.assertEqual(len(e.world.ants),8)
            e.advance(1)
            self.assertEqual(e.turn,1)

    def test_setup_seed_cap_validation_and_text_replacement(self):
        self.click('new')
        self.click('seed',True)
        self.event(key(pygame.K_4,'4'))
        self.event(key(pygame.K_2,'2'))
        self.click('cap',True)
        self.event(key(pygame.K_0,'0'))
        self.click('start')
        self.assertIsNone(self.app.engine)
        self.assertTrue(self.app.message)
        self.click('cap',True)
        self.event(key(pygame.K_3,'3'))
        self.click('start')
        self.assertEqual((self.app.engine.config.seed,self.app.engine.max_turns),(42,3))

    def test_space_mouse_pause_resume_and_paused_walltime_exclusion(self):
        self.start()
        self.app.frame(.25,[])
        e=self.app.engine
        self.assertAlmostEqual(e.progress,.25)
        self.event(key(pygame.K_SPACE))
        self.assertEqual(self.app.mode,'pause')
        snapshot=full_fingerprint(e)
        self.app.frame(120,[])
        self.assertEqual(full_fingerprint(e),snapshot)
        self.click('resume')
        self.assertAlmostEqual(e.progress,.25)
        self.assertEqual(e.turn,0)
        self.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=self.app.renderer.action_rects['pause'].center))
        self.assertTrue(e.paused)
        self.event(key(pygame.K_SPACE))
        self.assertFalse(e.paused)

    def test_repeat_does_not_double_toggle_space(self):
        self.start()
        self.event(key(pygame.K_SPACE))
        self.event(key(pygame.K_SPACE,repeat=True))
        self.assertTrue(self.app.engine.paused)

    def test_pre_pause_logical_debt_is_retained_without_paused_time(self):
        self.start()
        self.app.frame(0,[])
        self.event(key(pygame.K_SPACE),elapsed=2.5)
        self.assertEqual(self.app.engine.turn,0)
        self.assertAlmostEqual(self.app.pending_turns,2.5)
        self.app.frame(100,[])
        self.event(key(pygame.K_SPACE))
        self.assertEqual(self.app.engine.turn,1)
        self.assertAlmostEqual(self.app.engine.progress,1.5)
        self.app.frame(0,[])
        self.assertEqual(self.app.engine.turn,2)
        self.assertAlmostEqual(self.app.engine.progress,.5)

    def test_space_exits_cap_editor_and_still_pauses(self):
        self.start()
        self.event(key(pygame.K_t))
        self.assertEqual(self.app.mode,'cap')
        self.event(key(pygame.K_SPACE))
        self.assertIsNone(self.app.controls.cap_text)
        self.assertEqual(self.app.mode,'pause')
        self.event(key(pygame.K_SPACE))
        self.assertTrue(self.app.active)

    def test_clickable_cap_apply_cancel_and_end_results(self):
        self.start()
        self.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=self.app.renderer.action_rects['cap'].center))
        self.event(key(pygame.K_5,'5'))
        self.click('apply_cap')
        self.assertEqual(self.app.engine.max_turns,5)
        self.event(key(pygame.K_t))
        self.click('cancel_cap')
        self.assertEqual(self.app.engine.max_turns,5)
        self.app.engine.advance(5)
        self.app.draw()
        self.assertTrue(self.app.engine.ended)
        old=full_fingerprint(self.app.engine)
        self.app.action('menu_game')
        self.app.draw()
        self.assertNotIn('resume',self.app.buttons)
        self.event(key(pygame.K_ESCAPE))
        self.assertEqual(self.app.mode,'game')
        self.app.frame(20,[])
        self.assertEqual(old,full_fingerprint(self.app.engine))

    def test_restart_cleans_world_jobs_cache_selection_and_keeps_configuration(self):
        self.start()
        old=weakref.ref(self.app.engine.world)
        self.app.renderer.selected_id=self.app.engine.world.ants[0].id
        self.app.renderer.overlays.enabled['territory']=True
        self.app.renderer.draw(self.app.engine)
        self.app.engine.max_turns=99
        self.event(key(pygame.K_r))
        gc.collect()
        self.assertIsNone(old())
        self.assertEqual(self.app.engine.max_turns,99)
        self.assertEqual(self.app.engine.turn,0)
        self.assertFalse(self.app.engine.construction.tasks)
        self.assertIsNone(self.app.renderer.selected_id)
        self.assertTrue(self.app.renderer.overlays.enabled['territory'])

    def test_new_game_settings_do_not_advance_existing_world(self):
        self.start()
        self.event(key(pygame.K_SPACE))
        snapshot=full_fingerprint(self.app.engine)
        self.click('settings')
        self.click('fps_30')
        self.click('text_22')
        self.app.frame(20,[])
        self.assertEqual(snapshot,full_fingerprint(self.app.engine))
        self.click('back_settings')
        self.click('new_game')
        self.app.frame(120,[])
        self.assertEqual(snapshot,full_fingerprint(self.app.engine))
        self.click('size_128')
        self.click('start')
        self.assertEqual(self.app.engine.config.size,128)
        self.assertEqual(self.app.engine.turn,0)

    def test_middle_and_right_drag_grab_direction_and_boundaries(self):
        self.start()
        r,e=self.app.renderer,self.app.engine
        r.zoom=4
        camera.clamp(r,e)
        for mouse_button in (2,3):
            start=list(r.offset)
            self.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=mouse_button,pos=(300,300)))
            self.event(pygame.event.Event(pygame.MOUSEMOTION,pos=(350,340),rel=(50,40),buttons=(0,0,0)))
            self.assertAlmostEqual(r.offset[0]-start[0],50)
            self.assertAlmostEqual(r.offset[1]-start[1],40)
            self.event(pygame.event.Event(pygame.MOUSEBUTTONUP,button=mouse_button,pos=(350,340)))
            self.assertIsNone(self.app.controls.drag_button)
        camera.pan(r,e,(100000,-100000))
        viewport,scale,origin=r.geometry(e)
        self.assertLessEqual(origin[0],0)
        self.assertGreaterEqual(origin[0],viewport.w-e.config.size*scale)
        self.assertLessEqual(origin[1],0)
        self.assertGreaterEqual(origin[1],viewport.h-e.config.size*scale)

    def test_cursor_zoom_keeps_world_point_and_clamps_limits(self):
        self.start()
        r,e=self.app.renderer,self.app.engine
        r.zoom=4
        cursor=(400,350)
        _,scale,origin=r.geometry(e)
        world=((cursor[0]-origin[0])/scale,(cursor[1]-origin[1])/scale)
        self.event(pygame.event.Event(pygame.MOUSEWHEEL,y=1,x=0,pos=cursor))
        _,scale,origin=r.geometry(e)
        actual=((cursor[0]-origin[0])/scale,(cursor[1]-origin[1])/scale)
        for a,b in zip(world,actual): self.assertAlmostEqual(a,b)
        for factor in (1000,.00001):
            camera.zoom_at(r,e,factor,cursor)
            self.assertTrue(1<=r.zoom<=16)
        self.assertIsNone(r.selected_id)

    def test_drag_does_not_trigger_buttons_or_selection(self):
        self.start()
        r=self.app.renderer
        self.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3,pos=(300,300)))
        self.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=r.action_rects['pause'].center))
        self.assertFalse(self.app.engine.paused)
        self.assertIsNone(r.selected_id)

    def test_inspection_after_camera_movement(self):
        self.start()
        e,r=self.app.engine,self.app.renderer
        r.focus(e,0)
        camera.zoom_at(r,e,1.2,(100,100))
        a=e.world.ants[0]
        point=r.point(e,e.display_position(a))
        self.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=point))
        self.assertEqual(r.selected_id,a.id)

    def test_resize_small_window_scroll_and_overlay_controls(self):
        self.start()
        self.event(pygame.event.Event(pygame.VIDEORESIZE,w=800,h=600))
        for key_code in (pygame.K_s,pygame.K_p,pygame.K_c): self.event(key(key_code))
        self.assertTrue(all(self.app.renderer.overlays.enabled.values()))
        self.event(pygame.event.Event(pygame.MOUSEWHEEL,y=-20,x=0,pos=(700,300)))
        self.assertGreater(self.app.renderer.panel_scroll,0)
        self.assertTrue(self.app.renderer.panel_max_scroll)
        self.assertEqual(self.app.screen.get_size(),(800,600))
        self.event(pygame.event.Event(pygame.VIDEORESIZE,w=1600,h=900))
        self.app.draw()
        self.assertEqual(self.app.screen.get_size(),(1600,900))

    def test_ui_and_camera_do_not_change_deterministic_checkpoints(self):
        from simulation.engine import Engine
        self.start()
        reference=Engine(self.app.engine.config)
        for turn in range(12):
            for k in (pygame.K_s,pygame.K_p,pygame.K_c,pygame.K_g,pygame.K_h,pygame.K_RIGHT):
                self.event(key(k))
            self.app.engine.advance(1)
            reference.advance(1)
            self.app.draw()
            self.assertEqual(full_fingerprint(reference),full_fingerprint(self.app.engine))

    def test_repeated_game_creation_releases_old_worlds(self):
        worlds=[]
        for _ in range(4):
            self.app.start(Config(size=64))
            worlds.append(weakref.ref(self.app.engine.world))
            self.app.draw()
        gc.collect()
        self.assertTrue(all(ref() is None for ref in worlds[:-1]))

    def test_native_text_input_shortcuts_without_duplicate_keydown(self):
        self.start()
        self.event(pygame.event.Event(pygame.TEXTINPUT,text=' '))
        self.assertTrue(self.app.engine.paused)
        self.event(pygame.event.Event(pygame.TEXTINPUT,text=' '))
        self.assertFalse(self.app.engine.paused)
        self.event(key(pygame.K_SPACE,' '))
        self.event(pygame.event.Event(pygame.TEXTINPUT,text=' '))
        self.assertTrue(self.app.engine.paused)
        self.event(pygame.event.Event(pygame.TEXTINPUT,text='s'))
        self.assertTrue(self.app.renderer.overlays.enabled['scent'])

    def test_text_input_numeric_fields_do_not_duplicate_normal_keyboard(self):
        self.click('new')
        self.click('seed',field=True)
        self.event(key(pygame.K_4,'4'))
        self.event(pygame.event.Event(pygame.TEXTINPUT,text='4'))
        self.event(pygame.event.Event(pygame.TEXTINPUT,text='2'))
        self.assertEqual(self.app.draft_seed,'42')
        self.click('start')
        self.assertEqual(self.app.engine.config.seed,42)

    def test_focus_loss_pauses_and_releases_camera_drag(self):
        self.start()
        self.app.frame(0,[])
        self.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=2,pos=(200,200)))
        self.event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertEqual(self.app.mode,'pause')
        self.assertIsNone(self.app.controls.drag_button)
        turn=self.app.engine.turn
        self.app.frame(100,[])
        self.assertEqual(self.app.engine.turn,turn)

    def test_status_and_final_results_remain_fixed_while_panel_scrolls(self):
        self.start()
        self.event(pygame.event.Event(pygame.VIDEORESIZE,w=800,h=600))
        self.app.action('text_22')
        self.app.action('end')
        self.app.draw()
        region=pygame.Rect(472,144,310,4*(self.app.renderer.font.get_linesize()+3))
        before=pygame.image.tostring(self.app.screen.subsurface(region),'RGB')
        self.app.renderer.panel_scroll=100000
        self.app.draw()
        after=pygame.image.tostring(self.app.screen.subsurface(region),'RGB')
        self.assertEqual(before,after)
        self.assertTrue(self.app.renderer.panel_max_scroll)

    def test_boundaries_at_every_supported_zoom(self):
        self.start()
        r,e=self.app.renderer,self.app.engine
        for zoom in (1,1.2,2,4,8,16):
            r.zoom=zoom
            for delta in ((100000,-100000),(-100000,100000)):
                camera.pan(r,e,delta)
                viewport,scale,origin=r.geometry(e)
                extent=e.config.size*scale
                for available,coordinate in zip((viewport.w,viewport.h),origin):
                    if extent<=available:
                        self.assertAlmostEqual(coordinate,(available-extent)/2)
                    else:
                        self.assertLessEqual(coordinate,0)
                        self.assertGreaterEqual(coordinate,available-extent)

    def test_cli_defaults_explicit_options_and_gui_override(self):
        import main
        with patch.object(main,'run',return_value=None) as run:
            main.main([])
            self.assertFalse(run.call_args.args[2])
            main.main(['--size','128','--seed','42','--max-turns','7'])
            self.assertTrue(run.call_args.args[2])
            self.assertEqual(run.call_args.args[0].size,128)
            main.main(['--setup','--size','256'])
            self.assertFalse(run.call_args.args[2])
            self.assertEqual(run.call_args.args[0].size,256)

if __name__=='__main__': unittest.main()
