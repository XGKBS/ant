"""Supply Depot V2 autonomous validation. No entities or resources are injected."""
import argparse,json,os,statistics
from pathlib import Path
from time import perf_counter
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import numpy as np
from config import Config
from simulation.engine import Engine
from benchmarks.honeypots import fingerprint


def run(seed,size,turns,output,screenshots=False):
    e=Engine(Config(size=size,seed=seed))
    food=e.food.accounting()['residual'];soil=e.construction.soil_total()
    histories=[];events=[];participation=[];durations=[];seen=set();captures={}
    if screenshots:
        import pygame
        from ui.renderer import Renderer
        from ui import camera
        pygame.init();screen=pygame.display.set_mode((1450,1000));r=Renderer(screen,e)
    def capture(name,site=None,depot=None):
        before=fingerprint(e)
        r.overview();r.selected_id=r.selected_station=None;r.selected_site=site.id if site else None;r.selected_depot=depot.id if depot else None
        p=site.target if site else depot.position
        r.zoom=16
        viewport,scale,origin=r.geometry(e)
        r.offset=[viewport.w/2-(origin[0]+(p[0]+1)*scale),viewport.h/2-(origin[1]+(p[1]+1)*scale)]
        camera.clamp(r,e);r.panel_scroll=100000;r.draw(e)
        path=output/f'DEPOT_V2_{name.upper()}.png';pygame.image.save(screen,str(path));captures[name]=path.name
        assert before==fingerprint(e)
    for _ in range(turns):
        if e.ended:break
        start=perf_counter();e.advance(1);durations.append((perf_counter()-start)*1000)
        assert e.food.accounting()['residual']==food
        assert e.construction.soil_total()==soil
        assert np.all(e.world.terrain.occupancy<=e.world.terrain.capacity)
        assert np.all(e.world.terrain.occupancy>=0)
        for event in e.depots.events:
            key=json.dumps(event,sort_keys=True)
            if key not in seen:events.append(event);seen.add(key)
        for j in e.construction.tasks.values():
            if j.kind=='depot':
                participation.append(dict(turn=e.turn,project=j.id,faction=j.faction,work=int(j.progress),
                    active=j.active_builders,crew=j.crew.copy(),contributions=j.contributions.copy(),blocked=j.blocked_reason))
                if screenshots and 'construction' not in captures and 0<j.progress<20:
                    capture('construction',site=j)
        if screenshots and 'completed' not in captures:
            d=next((d for d in e.world.depots if d.deposited>0),None)
            if d is not None:capture('completed',depot=d)
        histories.append(dict(turn=e.turn,population=len(e.world.ants),reserves=[c.reserves for c in e.world.colonies],
            queens_alive=[c.alive for c in e.world.colonies],depots=len(e.world.depots),
            depot_delivered=sum(d.deposited for d in e.world.depots),
            queen_delivered=e.food.delivered-sum(d.deposited for d in e.world.depots)))
    done=[v for v in events if v['kind']=='completed']
    result=dict(seed=seed,size=size,requested_turns=turns,turns=e.turn,normal_initialization=True,
        proposals=sum(v['kind']=='proposal' for v in events),accepted=sum(v['kind']=='accepted' for v in events),
        completed=len(done),first_completion=min((v['turn'] for v in done),default=None),
        depot_delivered=sum(d.deposited for d in e.world.depots),queen_delivered=e.food.delivered-sum(d.deposited for d in e.world.depots),
        failures=dict(e.depots.failures),final_food=e.food.accounting(),initial_residual=food,
        initial_soil=soil,final_soil=e.construction.soil_total(),mean_ms=statistics.mean(durations),worst_ms=max(durations),
        captures=captures,final_fingerprint=fingerprint(e),events=events,builder_history=participation,balance_history=histories)
    if screenshots:
        r.overview();r.selected_depot=r.selected_site=None;r.draw(e)
        pygame.image.save(screen,str(output/'DEPOT_V2_OVERVIEW.png'));pygame.quit()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--size',type=int,default=512)
    p.add_argument('--turns',type=int,default=350);p.add_argument('--seeds',nargs='+',type=int,default=[7,19,42]);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);results=[]
    for seed in a.seeds:
        row=run(seed,a.size,a.turns,a.output,screenshots=seed==a.seeds[0]);results.append(row)
        (a.output/'DEPOT_V2_GAMEPLAY.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in row.items() if k not in ('events','builder_history','balance_history')}),flush=True)
if __name__=='__main__':main()
