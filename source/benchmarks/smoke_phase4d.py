"""Exercise the real main loop via SDL's event queue; capture review artifacts."""
import argparse, json, os
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--dummy',action='store_true');args=p.parse_args()
    if args.dummy:
        os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from config import Config
    from main import run
    args.output.mkdir(parents=True,exist_ok=True)
    log=[]; old=None
    def click(app,name):
        rect=app.buttons.get(name) or app.renderer.action_rects.get(name)
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=rect.center))
    def key(code,text=''):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=code,unicode=text))
    def capture(app,name):
        pygame.image.save(app.screen,str(args.output/('PHASE4D_'+name+'.png')))
        log.append({'frame':name,'mode':app.mode,'turn':None if app.engine is None else app.engine.turn})
    def hook(app,frame):
        nonlocal old
        if frame==0: capture(app,'MAIN');click(app,'new')
        elif frame==1: capture(app,'SETUP');click(app,'size_64')
        elif frame==2: click(app,'perk_heavy-lifting')
        elif frame==3: click(app,'start')
        elif frame==4:
            assert app.engine.world.config.size==64
            assert app.engine.world.colonies[0].perk=='heavy-lifting'
            app.engine.advance(8);old=app.engine
            capture(app,'ACTIVE');key(pygame.K_SPACE,' ')
        elif frame==5:
            assert app.engine.paused and app.mode=='pause';capture(app,'PAUSE');click(app,'settings')
        elif frame==6: capture(app,'SETTINGS');click(app,'text_22')
        elif frame==7: click(app,'back_settings')
        elif frame==8: click(app,'resume')
        elif frame==9:
            for code in (pygame.K_s,pygame.K_p,pygame.K_c,pygame.K_f):key(code)
        elif frame==10:
            assert all(app.renderer.overlays.enabled.values());capture(app,'OVERLAYS')
            pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL,y=2,x=0,pos=(300,300)))
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3,pos=(300,300)))
            pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION,pos=(350,340),rel=(50,40),buttons=(0,0,1)))
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP,button=3,pos=(350,340)))
        elif frame==11:
            assert app.controls.drag_button is None
            ant=app.engine.world.ants[0];app.renderer.focus(app.engine,ant.faction)
            app.draw();pos=app.renderer.point(app.engine,app.engine.display_position(ant))
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=pos))
        elif frame==12:
            assert app.renderer.selected_id is not None;capture(app,'INSPECTION')
            pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE,w=800,h=600))
        elif frame==13: capture(app,'SMALL');key(pygame.K_t,'t')
        elif frame==14:
            assert app.mode=='cap';capture(app,'TURN_CAP');click(app,'cancel_cap')
        elif frame==15: key(pygame.K_e,'e')
        elif frame==16:
            assert app.engine.ended;capture(app,'RESULTS');click(app,'restart')
        elif frame==17:
            assert app.engine is not old and app.engine.turn==0 and app.renderer.selected_id is None
            click(app,'new_game')
        elif frame==18:
            assert app.mode=='setup';click(app,'size_128')
        elif frame==19: click(app,'start')
        elif frame==20:
            assert app.engine.world.config.size==128;key(pygame.K_ESCAPE)
        elif frame==21: click(app,'quit')
    app=run(Config(),event_hook=hook,smoke_frames=30)
    assert not app.running
    (args.output/'PHASE4D_REAL_LOOP.json').write_text(json.dumps({'passed':True,'frames':22,'driver':'dummy' if args.dummy else 'native','observations':log},indent=2))
    print('Real main loop: 22 frames; setup, pause, settings, overlays, drag, zoom, inspection, resize, cap, end, restart, new game, quit passed.')
if __name__=='__main__':main()
