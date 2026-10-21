"""Complete model replay at every turn; full navigation state checked at the end."""
import os,json,hashlib
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
from config import Config
from simulation.engine import Engine
from benchmarks.phase4e import fingerprint as model_fingerprint
from benchmarks.phase4a import canonical
from benchmarks.honeypots import fingerprint as full_fingerprint
from ui.renderer import Renderer


def state(e):
    extra=[e.world.depots,e.information.last_turn,e.information.metrics,e.behavior.guard_ids,e.behavior.guard_slots,
           e.behavior.metrics,e.behavior.assignments,e.behavior.retries,e.behavior.excavation_claims,e.depots.savings,e.depots.last_proposal,
           e.exploration.routes,e.exploration.failed,e.orders.logistics,e.orders.received,e.food.pending_drops,e.honeypots.loaded,e.honeypots.healed]
    return hashlib.sha256((model_fingerprint(e)+json.dumps(canonical(extra),separators=(',',':'))).encode()).hexdigest()


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    pygame.init();screen=pygame.display.set_mode((1450,1000));a,b=Engine(Config(seed=7)),Engine(Config(seed=7));r=Renderer(screen,b)
    r.overlays.enabled.update(scent=True,pheromones=True,territory=True);checks=[]
    initial=a.food.accounting()['residual'];soil=a.construction.soil_total()
    for turn in range(1,501):
        a.advance(1);b.paused=True;b.advance(5);b.paused=False;b.advance(.25);b.advance(.75)
        if turn%25==0:
            before=state(b);r.focus(b,turn%4);r.draw(b);r.overview();r.draw(b);assert state(b)==before
        assert state(a)==state(b),(turn,'completed state mismatch')
        assert a.food.accounting()['residual']==initial and a.construction.soil_total()==soil
        if turn%100==0:checks.append(dict(turn=turn,state_sha256=state(a),ants=len(a.world.ants),depots=len(a.world.depots),food=a.food.accounting()))
    assert full_fingerprint(a)==full_fingerprint(b)
    expected=next(json.loads(line) for line in (args.output/'AUTONOMY_AFTER.jsonl').read_text().splitlines() if json.loads(line).get('label')=='natural' and json.loads(line).get('seed')==7)
    assert len(a.world.ants)==expected['final_ants'] and a.food.delivered==expected['delivered'] and a.information.metrics==expected['information']
    r=Renderer(screen,a);r.overview();r.draw(a);pygame.image.save(screen,str(args.output/'AUTONOMY_OVERVIEW.png'))
    chosen=max(a.world.ants,key=lambda ant:(len(ant.information),ant.stationary_turns,ant.id));r.selected_id=chosen.id
    r.zoom=16;viewport,scale,origin=r.geometry(a);r.offset=[viewport.w/2-(origin[0]+chosen.position[0]*scale),viewport.h/2-(origin[1]+chosen.position[1]*scale)]
    from ui.camera import clamp
    clamp(r,a);r.panel_scroll=100000;r.draw(a);pygame.image.save(screen,str(args.output/'AUTONOMY_INSPECTION.png'))
    final=full_fingerprint(a);a.reset();assert full_fingerprint(a)==full_fingerprint(Engine(a.config))
    (args.output/'AUTONOMY_REPLAY.json').write_text(json.dumps(dict(seed=7,size=512,turns=500,every_completed_model_state_equal=True,
        final_navigation_state_equal=True,pause_fps_overlay_equal=True,reset_equal=True,matches_natural_benchmark=True,checkpoints=checks,final_sha256=final),indent=2),encoding='utf-8')
    pygame.quit();print('500-turn model, navigation, pause/FPS/overlay and reset replay passed',flush=True)
if __name__=='__main__':main()
