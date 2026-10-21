"""Phase 4E comparable fixtures, complete economy checkpoints and subsystem costs."""
import argparse,hashlib,json,os,platform,gc,tracemalloc
from pathlib import Path
from time import perf_counter
from benchmarks.phase3 import populated
from benchmarks.phase4b import full_fingerprint
from benchmarks.phase4a import canonical
from benchmarks.phase4c import distribution

def working_set_bytes():
    """Read-only Windows process memory metric, no external dependency."""
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in
                 ('peak_working_set','working_set','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
    info=Counters();info.cb=ctypes.sizeof(info)
    kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(info),info.cb):
        raise ctypes.WinError()
    return info.working_set

def fingerprint(e):
    state=[full_fingerprint(e),e.world.stations,e.world.station_locations,
           e.supply.initial_units,e.supply.generated_units,e.supply.last_refill_units,e.supply.last_refill_turn,
           e.food.initial_units,e.food.generated_units,e.food.accounting()]
    return hashlib.sha256(json.dumps(canonical(state),separators=(',',':')).encode()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--counts',type=int,nargs='+',default=[100,500,1000]);p.add_argument('--turns',type=int,default=30);a=p.parse_args()
    os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame,numpy as np
    from ui.application import Application
    from ui.renderer import Renderer
    pygame.init();screen=pygame.display.set_mode((1200,800))
    with a.output.open('w',encoding='utf-8') as out:
        def emit(record):out.write(json.dumps(record)+'\n');out.flush();print(json.dumps({k:v for k,v in record.items() if k not in ('fingerprints','populations','reserves','turn_ms')}),flush=True)
        emit(dict(kind='environment',platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,pygame=pygame.version.ver,driver=pygame.display.get_driver(),seed=7,size=512,turns=a.turns))
        for count in a.counts:
            start=perf_counter();e=populated(count,'distributed',512);setup=perf_counter()-start
            initial_residual=e.food.accounting()['residual'];soil=e.construction.soil_total()
            timings=[];pops=[];reserves=[];hashes=[]
            for _ in range(a.turns):
                if e.ended:break
                start=perf_counter();e.advance(1);timings.append(perf_counter()-start)
                assert e.food.accounting()['residual']==initial_residual
                assert e.construction.soil_total()==soil
                assert np.all(e.world.terrain.occupancy<=e.world.terrain.capacity)
                pops.append(len(e.world.ants));reserves.append([c.reserves for c in e.world.colonies]);hashes.append(fingerprint(e))
            births=sum(c.produced_workers+c.produced_soldiers for c in e.world.colonies)
            deaths=e.lifecycle.ant_deaths
            # Profile extra turns separately, retaining the uninstrumented primary timings.
            costs={}
            restorations=[]
            def wrap(obj,name,label):
                original=getattr(obj,name)
                def measured(*args,**kwargs):
                    start=perf_counter()
                    try:return original(*args,**kwargs)
                    finally:
                        elapsed=perf_counter()-start
                        entry=costs.setdefault(label,[0,0]);entry[0]+=elapsed;entry[1]+=1
                        if label in ('upkeep','station_update') and args[0]%25==0:
                            entry=costs.setdefault(label+'_due',[0,0]);entry[0]+=elapsed;entry[1]+=1
                setattr(obj,name,measured)
                return original
            for obj,name,label in ((e.economy,'settle_upkeep','upkeep'),(e.economy,'survive','queen_survival'),(e.supply,'tick','station_update'),(e.fsm,'prepare','ai_prepare'),(e.fsm,'choose','ai_choose'),(e.fsm,'public_station','public_station_selection'),(e.food,'visible','food_observation')):
                restorations.append((obj,name,wrap(obj,name,label)))
            import ai.pathfinding as paths,ai.state_machine as states
            original=wrap(paths,'find_path','astar');old_alias=states.find_path;states.find_path=paths.find_path
            # Includes a due turn (50) without suppressing any intervening logical work.
            for _ in range(50-e.turn):
                if e.ended:break
                e.advance(1)
            paths.find_path=original;states.find_path=old_alias
            for obj,name,method in restorations:setattr(obj,name,method)
            e.paused=True;r=Renderer(screen,e);r.economy_open=True;r.focus(e,0)
            render={}
            for mode in ('none','all'):
                for name in r.overlays.enabled:r.overlays.enabled[name]=mode=='all'
                r.draw(e);samples=[]
                for _ in range(60):
                    start=perf_counter();r.draw(e);pygame.display.flip();samples.append(perf_counter()-start)
                render[mode]=distribution(samples)
            app=Application(screen);app.engine=e;app.renderer=r;app.mode='game';e.paused=False
            pygame.event.clear();pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE,unicode=' '))
            start=perf_counter();e.advance(1);blocked=perf_counter()-start;app.frame(0,pygame.event.get());latency=perf_counter()-start
            assert e.paused or e.ended
            gc.collect();tracemalloc.start();r.overlays.invalidate();r.draw(e);live,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            emit(dict(kind='benchmark',initial_ants=count,final_ants=pops[-1],turns=len(pops),setup_seconds=round(setup,4),simulation=distribution(timings),turn_ms=[round(t*1000,4) for t in timings],populations=pops,reserves=reserves,fingerprints=hashes,
                      births=births,deaths=deaths,
                      profiling_target_turn=50,actual_later_turn=e.turn,ended=e.ended,profile_costs={k:dict(total_ms=round(v[0]*1000,3),calls=v[1],mean_call_ms=round(v[0]*1000/v[1],6)) for k,v in costs.items()},
                      later_ants=len(e.world.ants),births_through_later_turn=sum(c.produced_workers+c.produced_soldiers for c in e.world.colonies),deaths_through_later_turn=e.lifecycle.ant_deaths,
                      food=e.food.accounting(),injected_residual=initial_residual,soil_total=e.construction.soil_total(),station_generated=e.supply.generated_units,
                      rendering=render,blocking_turn_ms=round(blocked*1000,3),queued_pause_ms=round(latency*1000,3),overlay_cache_bytes=r.overlays.cache_bytes(),python_overlay_live=live,python_overlay_peak=peak,process_working_set_bytes=working_set_bytes(),
                      note='Primary 30 turns uninstrumented; subsequent turns through 50 profile nested call costs (do not add A* to inclusive AI). Rendering at turn 50; controlled queued pause at turn 51; tracemalloc overlay refresh excludes SDL allocations.'))
            del e,r,app,obj
            gc.collect()
    pygame.quit()
if __name__=='__main__':main()
