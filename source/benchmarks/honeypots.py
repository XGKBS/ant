"""Default before/after fixtures and fixed-population supply/upkeep stress runs."""
import argparse,hashlib,json,platform,statistics
from pathlib import Path
from dataclasses import asdict
from time import perf_counter
import numpy as np
from config import Config
from simulation.engine import Engine
from entities.models import Ant
from benchmarks.phase3 import populated
from benchmarks.strategy_depots import fingerprint as previous_fingerprint
from benchmarks.phase4a import canonical
from benchmarks.phase4e import working_set_bytes


def fingerprint(e):
    extra=[e.food.pending_drops,e.food.dropped_units,e.food.direct_consumed,
           e.honeypots.loaded,e.honeypots.healed,e.honeypots.claims,
           e.exploration.seen,e.exploration.frontiers,e.exploration.roles,
           e.exploration.claims,e.exploration.failed,e.exploration.routes]
    extra += [e.information.last_turn,e.information.metrics,e.behavior.guard_ids,
              e.behavior.guard_slots,e.behavior.assignments,e.behavior.retries,e.behavior.excavation_claims,e.behavior.metrics]
    return hashlib.sha256((previous_fingerprint(e)+json.dumps(canonical(extra),separators=(',',':'))).encode()).hexdigest()


def supply_scene(count):
    e=Engine(Config(size=128,food_count=0,stone_density=0,large_stone_density=0,
                    reproduction_enabled=False,combat_enabled=False))
    w=e.world;w.ants.clear();w.terrain.occupancy[:]=0
    for faction,c in enumerate(w.colonies):
        q=c.queen.position;n=w.config.size
        xr=range(0,n//2-1) if q[0]<n//2 else range(n//2+1,n)
        yr=range(0,n//2-1) if q[1]<n//2 else range(n//2+1,n)
        candidates=[(x,y) for x in xr for y in yr if w.terrain.capacity[y,x]]
        candidates.sort(key=lambda p:((p[0]-q[0])**2+(p[1]-q[1])**2,p))
        for index,p in enumerate(candidates[:count//4+(faction<count%4)]):
            kind='honeypot' if index%20==19 else ('soldier' if index%4==0 else 'worker')
            a=Ant(w.allocate_id(),faction,p,kind=kind,stored_food=10 if kind=='honeypot' else 0)
            w.ants.append(a);w.terrain.occupancy[p[1],p[0]]+=1
        c.reserves=40
    assert len(w.ants)==count
    e._plan();return e


def measure(e,count,turns,kind):
    residual=e.food.accounting()['residual'];soil=e.construction.soil_total()
    durations=[];settlement=[]
    if kind=='active-supply':
        original=e.economy.settle_upkeep
        def measured(turn):
            if turn%100:return original(turn)
            start=perf_counter();original(turn);settlement.append((perf_counter()-start)*1000)
        e.economy.settle_upkeep=measured
    for turn in range(turns):
        if e.ended:break
        start=perf_counter();e.advance(1)
        assert np.all(e.world.terrain.occupancy<=e.world.terrain.capacity)
        durations.append((perf_counter()-start)*1000)
        assert e.food.accounting()['residual']==residual
        assert e.construction.soil_total()==soil
    if kind=='active-supply':assert len(e.world.ants)==count
    return dict(kind=kind,starting_ants=count,final_ants=len(e.world.ants),turns=e.turn,
                mean_ms=statistics.mean(durations),worst_ms=max(durations),
                turn_100_ms=durations[99] if len(durations)>99 else None,settlement_ms=settlement,
                honeypots=sum(a.kind=='honeypot' for a in e.world.ants),
                stored=sum(a.stored_food for a in e.world.ants),loaded=e.honeypots.loaded,
                source_upkeep=sum(c.upkeep_source_half for c in e.world.colonies)/2,
                honeypot_upkeep=sum(c.upkeep_honeypot_half for c in e.world.colonies)/2,
                personal_upkeep=sum(c.upkeep_personal_half for c in e.world.colonies)/2,
                shared_upkeep=sum(c.upkeep_shared_half for c in e.world.colonies)/2,
                delivered=e.food.delivered,food_residual=residual,soil_total=soil,
                births=sum(c.produced_workers+c.produced_soldiers+c.produced_honeypots for c in e.world.colonies),
                deaths=e.lifecycle.ant_deaths,expeditions=len(e.exploration.expedition_ids),
                visited_chunks=[len(s) for s in e.exploration.seen],navigation=dict(e.navigation.metrics),
                cache_bytes=e.navigation.cache_bytes(),working_set_bytes=working_set_bytes())


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--counts',type=int,nargs='+',default=[100,500,1000]);p.add_argument('--part',choices=['gameplay','supply','all'],default='all');args=p.parse_args()
    with args.output.open('w',encoding='utf-8') as out:
        def emit(row):out.write(json.dumps(row)+'\n');out.flush();print(json.dumps(row),flush=True)
        emit(dict(kind='environment',platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,seed=7,
                  note='Default: 512 map / 30 turns, reproduction/combat enabled. Active supply: 128 map / 110 turns, fixed ants; combat/reproduction disabled only for this diagnostic. Injections tracked by residual. Food/soil audits outside timing, occupancy inside.'))
        if args.part in ('gameplay','all'):
            for count in args.counts:emit(measure(populated(count,'distributed'),count,30,'gameplay'))
        if args.part in ('supply','all'):
            for count in args.counts:emit(measure(supply_scene(count),count,110,'active-supply'))

if __name__=='__main__':main()
