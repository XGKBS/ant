"""Strategic/depot integration timings and accounting; fixture injections are explicit."""
import argparse
import hashlib
import json
import platform
import statistics
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
import numpy as np
from config import Config
from simulation.engine import Engine
from entities.models import Ant, Food
from benchmarks.phase3 import populated
from benchmarks.phase4a import canonical
from benchmarks.phase4e import fingerprint as previous_fingerprint, working_set_bytes


def fingerprint(e):
    h = hashlib.sha256(previous_fingerprint(e).encode())
    state = [[asdict(d) for d in e.world.depots], e.orders.last_turn,
             sorted(e.orders.logistics), sorted(e.depots.logistics_workers),
             canonical(e.depots.known), canonical(e.depots.savings), canonical([vars(j) | {"progress": (j.progress.numerator,j.progress.denominator)} for j in e.construction.tasks.values()]),
             e.depots.last_proposal, e.depots.next_id, e.construction.next_id,
             sorted(e.world.structure_cells), sorted(e.world.depot_claims),
             sorted(e.depots.withdraw_claims.items()), sorted(e.depots.deposit_claims.items())]
    h.update(json.dumps(state, sort_keys=True).encode())
    for key, field in e.navigation.fields.items():
        h.update(repr((key, field.seeds, tuple(field.frontier), sorted(field.dependencies.items()), sorted(field.touched_chunks), field.revision, field.last_requested)).encode())
        h.update(field.distances.tobytes())
    for key, job in e.navigation.jobs.items():
        h.update(repr((key, job.frontier, sorted(job.costs.items()), sorted(job.parents.items()), job.expanded, job.revision, job.last_requested, job.done, job.result)).encode())
    h.update(repr((e.navigation.turn, e.navigation.remaining)).encode())
    return h.hexdigest()


def depot_scene(count):
    e = Engine(Config(size=128, stone_density=0, large_stone_density=0, food_count=0,
                      supply_stations_enabled=False, reproduction_enabled=False, combat_enabled=False))
    w = e.world
    w.ants.clear(); w.terrain.occupancy[:] = 0
    anchors = ((44,44), (81,44), (44,81), (81,81))
    for faction, anchor in enumerate(anchors):
        w.colonies[faction].reserves = 200
        job = e.construction.create(faction, 'depot', anchor)
        crew = [Ant(w.allocate_id(), faction, (anchor[0]-1,anchor[1]+dy)) for dy in range(2)]
        job.crew = [a.id for a in crew]
        for a in crew:
            a.construction_task=job.id;w.ants.append(a);w.terrain.occupancy[a.position[1],a.position[0]]=1
        for turn in range(1,11):
            for a in crew:a.action_used=False
            e.construction.resolve(turn)
        assert len(w.depots) == faction+1
        for a in crew:w.ants.remove(a);w.terrain.occupancy[a.position[1],a.position[0]]=0
        d = w.depots[-1]
        for p in ((anchor[0]-5,anchor[1]),(anchor[0],anchor[1]-5)):
            w.food.append(Food(w.allocate_id(),p,'large',500,16,age=16))
        candidates = [(x,y) for y in range(anchor[1]-12,anchor[1]+13) for x in range(anchor[0]-12,anchor[0]+13)]
        candidates.sort(key=lambda p:(abs(p[0]-anchor[0])+abs(p[1]-anchor[1]),p))
        size = count//4+(faction < count%4)
        for i,p in enumerate(candidates[:size]):
            a = Ant(w.allocate_id(),faction,p,kind='soldier' if i%4==0 else 'worker')
            a.known_food = {f.id:f.position for f in w.food[-2:]}
            w.ants.append(a);w.terrain.occupancy[p[1],p[0]] += 1
    assert len(w.ants) == count
    e.food.rebuild_scent();e._plan()
    return e


def measure(e, turns, kind, count):
    assert len(e.world.ants) == count
    initial = e.food.accounting()['residual'];soil = e.construction.soil_total()
    durations=[]
    for _ in range(turns):
        if e.ended:break
        start=perf_counter();e.advance(1)
        assert np.all(e.world.terrain.occupancy<=e.world.terrain.capacity)
        durations.append((perf_counter()-start)*1000)
        assert e.food.accounting()['residual']==initial
        assert e.construction.soil_total()==soil
    metrics=dict(e.navigation.metrics)
    # Isolate new per-turn bookkeeping on frozen ant positions, outside gameplay timing.
    micro={}
    for label, call in (('orders',lambda t:e.orders.propagate(t)),('depot_roles',lambda t:e.depots.begin_plan())):
        samples=[]
        for i in range(25):
            start=perf_counter();call(e.turn+i+1);samples.append((perf_counter()-start)*1000)
        micro[label+'_mean_ms']=statistics.mean(samples)
    return dict(kind=kind,starting_ants=count,final_ants=len(e.world.ants),turns=len(durations),
                mean_ms=statistics.mean(durations),worst_ms=max(durations),
                births=sum(c.produced_workers+c.produced_soldiers for c in e.world.colonies),
                deaths=e.lifecycle.ant_deaths,depots=len(e.world.depots),
                depot_deposits=sum(d.deposited for d in e.world.depots),
                depot_withdrawals=0,
                delivered=e.food.delivered,food_residual=initial,soil_total=soil,
                navigation=metrics,navigation_cache_bytes=e.navigation.cache_bytes(),
                working_set_bytes=working_set_bytes(),bookkeeping_micro=micro)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--counts',nargs='+',type=int,default=[100,500,1000]);p.add_argument('--part',choices=['gameplay','depots','all'],default='all')
    args=p.parse_args()
    with args.output.open('w',encoding='utf-8') as out:
        def emit(data):
            out.write(json.dumps(data)+'\n');out.flush();print(json.dumps(data),flush=True)
        emit(dict(kind='environment',platform=platform.platform(),python=platform.python_version(),seed=7,
                  gameplay_map=512,gameplay_turns=30,depot_map=128,depot_turns=60,
                  note='Uninstrumented inclusive logical turns. Food/soil audits outside timing. Depot scene is staged; reproduction/combat disabled to hold population fixed. Micro timings run after gameplay on frozen positions.'))
        if args.part in ('gameplay','all'):
            for count in args.counts:emit(measure(populated(count,'distributed'),30,'gameplay',count))
        if args.part in ('depots','all'):
            for count in args.counts:emit(measure(depot_scene(count),60,'active-depots',count))

if __name__=='__main__':main()
