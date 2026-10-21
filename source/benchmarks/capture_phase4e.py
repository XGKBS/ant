"""Actual main-loop capture/audit; starvation scene is explicitly staged."""
import argparse,json,os
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from main import run
    from config import Config
    from benchmarks.phase4e import fingerprint
    from ui.food_economy import economy_lines
    a.output.mkdir(parents=True,exist_ok=True);log=[];hashes=[]
    def click(app,rect):pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=rect.center))
    def save(app,label):
        pygame.image.save(app.screen,str(a.output/('PHASE4E_'+label+'.png')))
        log.append(dict(scene=label,turn=app.engine.turn,food=app.engine.food.accounting(),reserves=[c.reserves for c in app.engine.world.colonies]))
    def hook(app,frame):
        if frame==0:click(app,app.buttons['new'])
        elif frame==1:click(app,app.buttons['size_64'])
        elif frame==2:click(app,app.buttons['start'])
        elif frame==3:
            for _ in range(55):app.engine.advance(1);hashes.append(fingerprint(app.engine))
            app.draw();save(app,'ACTIVE');click(app,app.renderer.economy_rect)
        elif frame==4:
            assert app.renderer.economy_open
            # Expose the economy section while retaining existing overlay controls.
            app.renderer.overlays.menu_open=False;app.draw();save(app,'ECONOMY')
            s=app.engine.world.stations[0];app.renderer.inspect(app.engine,app.renderer.point(app.engine,s.position))
        elif frame==5:save(app,'STATION')
        elif frame==6:
            app.engine.world.colonies[0].reserves=-20;app.engine.world.colonies[0].queen.hp=42
            app.engine.advance(1);app.renderer.selected_station=None;app.renderer.panel_scroll=0
            app.draw();save(app,'STARVATION')
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE,unicode=' '))
        elif frame==7:
            assert app.engine.paused
            snapshot=fingerprint(app.engine);app.frame(100,[]);assert snapshot==fingerprint(app.engine)
            click(app,app.buttons['resume'])
        elif frame==8:
            pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE,w=800,h=600))
            for key in (pygame.K_s,pygame.K_p,pygame.K_c):pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=key,unicode=''))
        elif frame==9:save(app,'SMALL_OVERLAYS');click(app,app.renderer.action_rects['restart'])
        elif frame==10:
            assert len(app.engine.world.stations)==12 and app.engine.supply.generated_units==0
            for expected in hashes:app.engine.advance(1);assert fingerprint(app.engine)==expected
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_e,unicode='e'))
        elif frame==11:
            assert app.engine.ended;save(app,'RESULTS');pygame.event.post(pygame.event.Event(pygame.QUIT))
    app=run(Config(),event_hook=hook,smoke_frames=15)
    assert not app.running
    (a.output/'PHASE4E_SMOKE.json').write_text(json.dumps(dict(passed=True,actual_main_loop=True,driver='dummy',replayed_turns=55,observations=log),indent=2))
    (a.output/'PHASE4E_REPLAY.json').write_text(json.dumps(dict(seed=7,size=64,default_mechanics=True,turns=55,restart_matches_every_turn=True,fingerprints=hashes),indent=2))
    print('Phase 4E main-loop smoke passed; 55 default-mechanics checkpoints reproduced after restart.')
if __name__=='__main__':main()
