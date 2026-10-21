"""Staged food-cluster demo, with real autonomous construction and physical transport."""
import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
from config import Config
from simulation.engine import Engine
from entities.models import Ant, Food
from benchmarks.strategy_depots import fingerprint
from ui.renderer import Renderer


def demo():
    e=Engine(Config(size=64,food_count=0,stone_density=0,large_stone_density=0,
                    supply_stations_enabled=False,reproduction_enabled=False,combat_enabled=False))
    w=e.world;w.ants.clear();w.terrain.occupancy[:]=0;w.colonies[0].reserves=30
    for p in ((30,30),(34,30)):
        w.food.append(Food(w.allocate_id(),p,'large',25,16,age=16))
    for p in ((29,30),(29,31),(30,32),(32,30)):
        a=Ant(w.allocate_id(),0,p);w.ants.append(a);w.terrain.occupancy[p[1],p[0]]+=1
    e.food.rebuild_scent();e._plan()
    return e


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    pygame.init();screen=pygame.display.set_mode((1200,900));a,b=demo(),demo()
    r=Renderer(screen,b);r.overlays.enabled.update(scent=True,pheromones=True,territory=True)
    initial=a.food.accounting()['residual'];soil=a.construction.soil_total();checkpoints=[]
    for turn in range(1,131):
        a.advance(1)
        b.paused=True;b.advance(10);b.paused=False;b.advance(.25);b.advance(.75)
        if turn%7==0:
            before=fingerprint(b);r.draw(b);assert before==fingerprint(b)
        assert fingerprint(a)==fingerprint(b)
        assert a.food.accounting()['residual']==initial
        assert a.construction.soil_total()==soil
        if turn in (10,30,60,100,130):
            checkpoints.append(dict(turn=turn,sha256=fingerprint(a),queen_food=a.world.colonies[0].reserves,
                                    depots=[asdict(d) for d in a.world.depots]))
    # Final capture has no overlays, exposing depot outline and real traffic clearly.
    r=Renderer(screen,a);r.draw(a)
    pygame.image.save(screen,str(args.output_dir/'STRATEGY_DEPOT_DEMO.png'))
    r.economy_open=True;r.draw(a)
    pygame.image.save(screen,str(args.output_dir/'STRATEGY_DEPOT_ECONOMY.png'))
    result=dict(note='Staged 64x64 cluster with 30 injected queen food and two injected food sources. Reproduction/combat disabled to isolate real construction and logistics, not a natural growth claim.',
                paired_render_pause_replay=True,initial_food_residual=initial,soil_total=soil,
                delivered=a.food.delivered,checkpoints=checkpoints)
    (args.output_dir/'STRATEGY_DEPOT_REPLAY.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    pygame.quit();print(json.dumps(dict(delivered=a.food.delivered,depots=len(a.world.depots),replay=True)))

if __name__=='__main__':main()
