"""Actual autonomous loading, source/supplier upkeep and deterministic neutral death-drop demo."""
import argparse,json,os
from pathlib import Path
from dataclasses import asdict
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
from config import Config
from entities.models import Ant,Food
from simulation.engine import Engine
from benchmarks.honeypots import fingerprint
from ui.renderer import Renderer
from ui import camera


def demo():
    e=Engine(Config(size=64,stone_density=0,large_stone_density=0,food_count=0,
                    supply_stations_enabled=False,reproduction_enabled=False,combat_enabled=False,
                    exploration_start_turn=0))
    w=e.world;w.ants.clear();w.terrain.occupancy[:]=0;w.colonies[0].reserves=30
    for p,kind in (((22,24),'worker'),((23,24),'worker'),((25,25),'honeypot'),((26,25),'soldier')):
        a=Ant(w.allocate_id(),0,p,kind=kind);w.ants.append(a);w.terrain.occupancy[p[1],p[0]]+=1
    w.food.append(Food(w.allocate_id(),(22,24),'large',25,16,age=16))
    e.food.rebuild_scent();e._plan();return e


def snapshot(e):
    return dict(turn=e.turn,sha256=fingerprint(e),queen_food=[c.reserves for c in e.world.colonies],
                honeypots=[dict(id=a.id,position=a.position,state=a.state,stored=a.stored_food) for a in e.world.ants if a.kind=='honeypot'],
                source_upkeep=sum(c.upkeep_source_half for c in e.world.colonies)/2,
                supplier_upkeep=sum(c.upkeep_honeypot_half for c in e.world.colonies)/2,
                loaded=e.honeypots.loaded,food=e.food.accounting())


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    pygame.init();screen=pygame.display.set_mode((1200,900));a,b=demo(),demo();r=Renderer(screen,b)
    r.overlays.enabled.update(scent=True,pheromones=True,territory=True)
    initial=a.food.accounting()['residual'];soil=a.construction.soil_total();checkpoints=[]
    for turn in range(1,111):
        a.advance(1);b.paused=True;b.advance(10);b.paused=False;b.advance(.25);b.advance(.75)
        if turn%9==0:
            before=fingerprint(b);r.draw(b);assert before==fingerprint(b)
        assert fingerprint(a)==fingerprint(b)
        assert a.food.accounting()['residual']==initial and a.construction.soil_total()==soil
        if turn in (25,50,99,100,110):checkpoints.append(snapshot(a))
    r=Renderer(screen,a);r.draw(a);pygame.image.save(screen,str(args.output_dir/'HONEYPOT_OVERVIEW.png'))
    h=next(a for a in a.world.ants if a.kind=='honeypot');r.selected_id=h.id
    camera.zoom_at(r,a,3,r.point(a,h.position));r.panel_scroll=100000;r.draw(a)
    pygame.image.save(screen,str(args.output_dir/'HONEYPOT_INSPECTION.png'))
    held=h.stored_food
    for e in (a,b):
        # Staged fatal event at committed positions, before replanning reservations.
        e.world.terrain.occupancy[:]=0
        for ant in e.world.ants:
            ant.path=[ant.position];e.world.terrain.occupancy[ant.position[1],ant.position[0]]+=1
        h=next(ant for ant in e.world.ants if ant.kind=='honeypot');h.hp=0;e.lifecycle.cleanup(e.turn)
        drops=[f for f in e.world.food if f.tier=='drop']
        assert sum(f.units for f in drops)==held
        e.food.rebuild_scent();e._plan()
        assert e.food.accounting()['residual']==initial
    assert fingerprint(a)==fingerprint(b)
    result=dict(note='Staged 64x64 cluster: two workers, one soldier, one empty Honeypot, 25 source food and 30 queen food. Real autonomous loading/upkeep; combat and reproduction disabled for isolation. Fatal event induced after turn 110.',
                paired_replay=True,overlay_and_pause_equivalence=True,initial_residual=initial,soil_total=soil,
                checkpoints=checkpoints,inventory_immediately_before_death=held,
                neutral_drop_units=sum(f.units for f in a.world.food if f.tier=='drop'),after_death=snapshot(a))
    (args.output_dir/'HONEYPOT_REPLAY.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    pygame.quit();print(json.dumps(dict(replay=True,loaded=a.honeypots.loaded,death_inventory=held,neutral_drop=result['neutral_drop_units'])))

if __name__=='__main__':main()
