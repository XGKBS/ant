"""Paired V2 replay and frozen rendering costs; all audits are outside timings."""
import os,json,statistics,gc
from pathlib import Path
from time import perf_counter
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
from config import Config
from simulation.engine import Engine
from benchmarks.honeypots import fingerprint
from benchmarks.strategy_depots import depot_scene
from benchmarks.phase4e import working_set_bytes
from ui.renderer import Renderer


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    pygame.init();screen=pygame.display.set_mode((1450,1000))
    a,b=Engine(Config(seed=7)),Engine(Config(seed=7));r=Renderer(screen,b)
    r.overlays.enabled.update(scent=True,pheromones=True,territory=True)
    checks=[]
    for turn in range(1,351):
        a.advance(1);b.paused=True;b.advance(8);b.paused=False;b.advance(.25);b.advance(.75)
        if turn%7==0:
            before=fingerprint(b);r.focus(b,turn%4);r.draw(b);r.overview();r.draw(b);assert fingerprint(b)==before
        assert fingerprint(a)==fingerprint(b),(turn,'replay mismatch')
        if turn in (1,50,100,200,350):checks.append(dict(turn=turn,sha256=fingerprint(a),depots=len(a.world.depots),depot_delivered=sum(d.deposited for d in a.world.depots)))
    expected=json.loads((args.output/'DEPOT_V2_GAMEPLAY.json').read_text(encoding='utf-8'))[0]['final_fingerprint']
    assert fingerprint(a)==expected,'normal/replay workload mismatch'
    assert a.depots.completed>0 and sum(d.deposited for d in a.world.depots)>0
    a.reset();assert fingerprint(a)==fingerprint(Engine(a.config))
    result=dict(seed=7,size=512,turns=350,completed_turn_states_equal=True,render_pause_fps_equal=True,
                reset_equal=True,matches_normal_gameplay=True,checkpoints=checks)
    (args.output/'DEPOT_V2_REPLAY.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    del a,b,r;gc.collect()
    e=depot_scene(1000)
    for _ in range(20):e.advance(1)
    r=Renderer(screen,e);before=fingerprint(e);memory=working_set_bytes();rows=[]
    for name in ('none','scent','pheromones','territory','all'):
        r.overview();r.overlays.enabled.update({k:name=='all' or k==name for k in r.overlays.enabled});r.overlays.invalidate()
        start=perf_counter();r.draw(e);cold=(perf_counter()-start)*1000
        times=[]
        for _ in range(30):
            start=perf_counter();r.draw(e);times.append((perf_counter()-start)*1000)
        assert fingerprint(e)==before
        rows.append(dict(mode=name,cold_ms=cold,cached_mean_ms=statistics.mean(times),cached_worst_ms=max(times)))
    render=dict(size=128,ants=1000,turn=e.turn,screen=[1450,1000],driver=pygame.display.get_driver(),
                note='Frozen staged four-depot world; rendering only. Cold includes raster/cache rebuild; cached uses same world. Software dummy display excludes real GPU/compositor/input latency.',
                rows=rows,working_set_before=memory,working_set_after=working_set_bytes(),read_only=True)
    (args.output/'DEPOT_V2_RENDERING.json').write_text(json.dumps(render,indent=2),encoding='utf-8');pygame.quit()
    print(json.dumps(dict(replay=True,checkpoints=checks,rendering=rows)),flush=True)
if __name__=='__main__':main()
