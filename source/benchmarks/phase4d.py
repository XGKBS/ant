"""Phase 4D UI input/render costs, without changing simulation algorithms."""
import argparse,json,os
from pathlib import Path
from time import perf_counter
from benchmarks.phase3 import populated
from benchmarks.phase4b import full_fingerprint
from benchmarks.phase4c import distribution,settings

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--frames',type=int,default=60);a=p.parse_args()
    os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from ui.application import Application
    from ui.renderer import Renderer
    pygame.init();screen=pygame.display.set_mode((1200,800),pygame.RESIZABLE)
    with a.output.open('w') as out:
        for count in (100,500,1000):
            e=populated(count,'distributed',512)
            for _ in range(5):e.advance(1)
            app=Application(screen);app.engine=e;app.renderer=Renderer(screen,e);app.mode='game'
            e.paused=True;app.renderer.focus(e,0)
            checkpoint=full_fingerprint(e)
            sample_ants=len(e.world.ants)
            results={}
            for mode in ('none','all'):
                settings(app.renderer,mode);app.draw();samples=[]
                for _ in range(a.frames):
                    t=perf_counter();app.draw();pygame.display.flip();samples.append(perf_counter()-t)
                results['cached_'+mode]=distribution(samples)
                samples=[]
                for _ in range(5):
                    app.renderer.overlays.invalidate();t=perf_counter();app.draw();samples.append(perf_counter()-t)
                results['refresh_'+mode]=distribution(samples)
            for operation in ('drag','zoom','pause'):
                samples=[]
                for i in range(30):
                    if operation=='drag':
                        events=[pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3,pos=(300,300)),pygame.event.Event(pygame.MOUSEMOTION,pos=(305 if i%2 else 295,300),rel=(5,0),buttons=(0,0,1)),pygame.event.Event(pygame.MOUSEBUTTONUP,button=3,pos=(300,300))]
                    elif operation=='zoom':events=[pygame.event.Event(pygame.MOUSEWHEEL,x=0,y=1 if i%2 else -1,pos=(300,300))]
                    else:events=[pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE,unicode=' ')]
                    t=perf_counter();app.frame(0,events);handled=perf_counter()-t;app.draw();samples.append(perf_counter()-t)
                    if operation=='pause':assert app.engine.paused==(i%2!=0)
                results[operation+'_event_and_draw']=distribution(samples)
            assert full_fingerprint(e)==checkpoint
            # An input arriving immediately after polling must wait for this
            # synchronous turn. It is processed before any following turn.
            e.paused=False;app.mode='game';pygame.event.clear()
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE,unicode=' '))
            t=perf_counter();e.advance(1);turn_time=perf_counter()-t
            app.frame(0,pygame.event.get());latency=perf_counter()-t
            assert e.paused
            record={'kind':'ui_responsiveness','size':512,'seed':7,'initial_ants':count,'sample_turn':5,'sample_ants':sample_ants,'after_blocking_turn_ants':len(e.world.ants),'frames':a.frames,**results,'blocking_turn_ms':round(turn_time*1000,3),'queued_pause_latency_ms':round(latency*1000,3),'note':'Controlled SDL queue latency, excluding OS scheduling; max one complete unchanged simulation turn per frame. No turn work discarded.'}
            out.write(json.dumps(record)+'\n');out.flush();print(json.dumps(record),flush=True)
    pygame.quit()
if __name__=='__main__':main()
