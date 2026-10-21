"""Matched autonomy timing, observational idle classes and natural-world audits."""
import argparse,cProfile,json,pstats,statistics,platform
from pathlib import Path
from time import perf_counter
from collections import Counter,deque
import numpy as np
from config import Config
from simulation.engine import Engine
from benchmarks.phase3 import populated


def summary(times):
 return dict(mean_ms=statistics.mean(times),median_ms=statistics.median(times),p95_ms=float(np.percentile(times,95)),worst_ms=max(times))


def classify(ant,moved,action,state,target,status):
 if action or moved:return 'productive'
 if state in ('guard','hold-defense','honeypot-hold','patrol-hold'):return 'strategic_stationary'
 if status=='pending' or 'plan' in state or state in ('build-depot','move-stone','compose-stone','gather','deliver-honeypot'):return 'waiting_dependency'
 if target is not None or ant.blocked_turns>=2:return 'temporarily_blocked'
 return 'unproductive_idle'


def measure(e,turns,label):
 starting=len(e.world.ants)
 food=e.food.accounting()['residual'];soil=e.construction.soil_total();times=[];classes=Counter();visited=set();discoveries=set();oscillations=0;stuck=0;history={};pops=[]
 for _ in range(turns):
  if e.ended:break
  prior={a.id:(a.position,a.state,a.target,a.navigation_status,any(x!=y for x,y in zip(a.path,a.path[1:])),tuple(a.path)) for a in e.world.ants}
  start=perf_counter();e.advance(1);times.append((perf_counter()-start)*1000)
  assert e.food.accounting()['residual']==food
  assert e.construction.soil_total()==soil
  assert np.all((e.world.terrain.occupancy>=0)&(e.world.terrain.occupancy<=e.world.terrain.capacity))
  pops.append(len(e.world.ants))
  for a in e.world.ants:
   if a.id not in prior:continue
   pos,state,target,status,moved,path=prior[a.id];action=a.last_action_turn==e.turn and a.last_action is not None
   activity=classify(a,moved,action,state,target,status);classes[activity]+=1
   for p in path:visited.add((a.faction,p))
   discoveries.update(a.food_observations)
   if a.blocked_turns==10 and activity=='temporarily_blocked':stuck+=1
   h=history.setdefault(a.id,deque(maxlen=4));h.append(a.position)
   if len(h)==4 and h[0]==h[2] and h[1]==h[3] and h[0]!=h[1] and not action and state not in ('guard','hold-defense','honeypot-hold','patrol-hold'):oscillations+=1
  live={a.id for a in e.world.ants};history={i:h for i,h in history.items() if i in live}
 info=getattr(e.world,'information',None)
 return dict(label=label,size=e.config.size,seed=e.config.seed,turns=e.turn,starting_ants=starting,final_ants=len(e.world.ants),timing=summary(times),
  turn_ms=times,populations=pops,idle_classes=dict(classes),observed_cells=len(visited),food_discoveries=len(discoveries),harvested=e.food.harvested,delivered=e.food.delivered,
  depot_food=sum(d.deposited for d in e.world.depots),depots=len(e.world.depots),excavated=e.world.terrain.excavated_units,construction=dict(e.construction.completed),
  stuck_events=stuck,oscillation_events=oscillations,queen_orders_received=e.orders.received,information=dict(info.metrics) if info else {},
  food_residual=e.food.accounting()['residual'],soil_total=soil,births=sum(c.produced_workers+c.produced_soldiers+c.produced_honeypots for c in e.world.colonies),
  deaths=e.lifecycle.ant_deaths,navigation=dict(e.navigation.metrics),navigation_cache_bytes=e.navigation.cache_bytes(),
  navigation_fields=len(e.navigation.fields),navigation_jobs=len(e.navigation.jobs),
  max_information_records=max((len(getattr(a,'information',{})) for a in e.world.ants),default=0),
  final_kind_counts=dict(Counter(a.kind for a in e.world.ants)))


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--part',choices=['all','population','natural','profile'],default='all');p.add_argument('--repeats',type=int,default=3);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',encoding='utf-8') as f:
  def emit(row):f.write(json.dumps(row)+'\n');f.flush();print(json.dumps({k:v for k,v in row.items() if k not in ('turn_ms','populations','navigation')}),flush=True)
  emit(dict(label='environment',platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,note='Inclusive advance(1), audits/metrics outside timing; 512 map; initial population fixtures seed7/30turns, natural seeds7/19/42/500turns.'))
  if a.part in ('all','population'):
   for repeat in range(a.repeats):
    for count in (100,500,1000):
     row=measure(populated(count,'distributed'),30,'population');row.update(starting_ants=count,repeat=repeat);emit(row)
  if a.part in ('all','natural'):
   for seed in (7,19,42):emit(measure(Engine(Config(size=512,seed=seed)),500,'natural'))
  if a.part in ('all','profile'):
   e=populated(1000,'distributed');profile=cProfile.Profile();profile.enable()
   for _ in range(20):e.advance(1)
   profile.disable();profile.dump_stats(str(a.output.with_suffix('.prof')))
   with a.output.with_suffix('.profile.txt').open('w',encoding='utf-8') as stream:pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(40)
if __name__=='__main__':main()
