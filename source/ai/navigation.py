"""Deterministic, budgeted shared reverse fields plus resumable local A*.

Global fields ignore transient occupancy. Every actual hop is still arbitrated
against live capacity by Engine. Only traversability changes invalidate fields;
their dependency chunks include a halo for newly opened boundary cells.
"""
from array import array
from collections import OrderedDict, Counter, deque
from heapq import heappush, heappop
from copy import copy, deepcopy
from ai.pathfinding import distance, neighbors

class Field:
    def __init__(self, terrain, seeds):
        self.width = terrain.capacity.shape[1]
        self.distances = array('i',[-1])*(terrain.capacity.size)
        self.frontier = deque()
        self.dependencies = {}
        self.touched_chunks = set()
        self.revision = terrain.topology_revision
        self.seeds = tuple(seeds)
        self.last_requested = 0
        for x,y in seeds:
            if terrain.capacity[y,x]:
                i=y*self.width+x
                self.distances[i]=0
                self.frontier.append(i)
                cx,cy=x//16,y//16
                for ox,oy in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
                    a,b=cx+ox,cy+oy
                    if 0<=a<terrain.navigation_chunks.shape[1] and 0<=b<terrain.navigation_chunks.shape[0]:
                        self.dependencies[(a,b)]=int(terrain.navigation_chunks[b,a])

    def valid(self,t):
        if self.revision == t.topology_revision:
            return True
        if any(int(t.navigation_chunks[y,x])!=v for (x,y),v in self.dependencies.items()):
            return False
        self.revision=t.topology_revision
        return True

    def expand(self,t,budget):
        w=self.width;h=t.capacity.shape[0];capacity=memoryview(t.capacity).cast('B')
        distances=self.distances;queue=self.frontier;used=0
        while queue and used<budget:
            i=queue.popleft();y,x=divmod(i,w);value=distances[i]+1;used+=1
            chunk=(x//16,y//16)
            if chunk not in self.touched_chunks:
                self.touched_chunks.add(chunk)
                cx,cy=chunk
                for ox,oy in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
                    a,b=cx+ox,cy+oy
                    if 0<=a<t.navigation_chunks.shape[1] and 0<=b<t.navigation_chunks.shape[0]:
                        self.dependencies.setdefault((a,b),int(t.navigation_chunks[b,a]))
            for q in ((i+1 if x+1<w else -1),(i+w if y+1<h else -1),
                      (i-1 if x else -1),(i-w if y else -1)):
                if q>=0 and capacity[q] and distances[q]<0:
                    distances[q]=value;queue.append(q)
        return used

    def __deepcopy__(self,memo):
        result=copy(self);memo[id(self)]=result
        result.distances=self.distances[:];result.frontier=self.frontier.copy()
        result.dependencies=self.dependencies.copy()
        result.touched_chunks=self.touched_chunks.copy()
        return result

class LocalSearch:
    def __init__(self,start,goal,revision,turn):
        self.start,self.goal=start,goal
        self.revision=revision;self.last_requested=turn
        self.frontier=[(distance(start,goal),0,start)]
        self.costs={start:0};self.parents={}
        self.expanded=0;self.result=None;self.done=False

    def expand(self,t,budget,limit):
        used=0
        while self.frontier and used<budget and self.expanded<limit:
            _,negative,p=heappop(self.frontier);cost=-negative
            if self.costs.get(p)!=cost:continue
            if p==self.goal:
                route=[]
                while p!=self.start:route.append(p);p=self.parents[p]
                self.result=route[::-1];self.done=True;break
            used+=1;self.expanded+=1
            for q in neighbors(t,p):
                candidate=cost+1
                if candidate<self.costs.get(q,10**12):
                    self.costs[q]=candidate;self.parents[q]=p
                    heappush(self.frontier,(candidate+distance(q,self.goal),-candidate,q))
        if not self.frontier or self.expanded>=limit:self.done=True
        return used

    def __deepcopy__(self,memo):
        result=copy(self);memo[id(self)]=result
        result.frontier=self.frontier.copy();result.costs=self.costs.copy();result.parents=self.parents.copy()
        result.result=None if self.result is None else self.result.copy()
        return result

class Navigation:
    def __init__(self,world):
        self.world=world
        self.fields=OrderedDict();self.jobs=OrderedDict();self.metrics=Counter()
        self.turn=-1;self.remaining=0
        self.station_positions={s.position for s in world.stations}
        self.station_ids={s.id for s in world.stations}
        self.station_assignments=Counter()
        self.home_cache={}

    def begin_turn(self,turn):
        if self.turn==turn:return
        self.turn=turn;self.remaining=self.world.config.navigation_node_budget
        self.station_assignments=Counter((a.faction,a.food_id) for a in self.world.ants if a.hp>0 and not a.cargo)
        for key,job in list(self.jobs.items()):
            if job.last_requested<turn-1:
                del self.jobs[key];self.metrics['cancelled_jobs']+=1
        # Stable insertion order and a guaranteed quantum prevent starvation.
        for key,field in list(self.fields.items()):
            if field.last_requested>=turn-1 and field.frontier:
                if not field.valid(self.world.terrain):
                    field=self.fields[key]=Field(self.world.terrain,field.seeds)
                    self.metrics['field_invalidations']+=1
                self._expand_field(field)

    def _expand_field(self,field):
        used=field.expand(self.world.terrain,min(self.remaining,self.world.config.navigation_quantum))
        self.remaining-=used;self.metrics['field_nodes']+=used

    def field(self,key,seeds):
        t=self.world.terrain;field=self.fields.get(key)
        self.metrics['field_requests']+=1
        if field is not None and (field.seeds!=tuple(seeds) or not field.valid(t)):
            del self.fields[key];field=None;self.metrics['field_invalidations']+=1
        if field is None:
            while len(self.fields)>=self.world.config.navigation_cache_fields:
                self.fields.popitem(last=False);self.metrics['field_evictions']+=1
            field=Field(t,seeds);self.fields[key]=field;self.metrics['field_builds']+=1
        else:
            self.metrics['field_hits']+=1;self.fields.move_to_end(key)
        field.last_requested=self.turn
        return field

    def home(self,faction):
        cached=self.home_cache.get(faction)
        if cached is not None and cached[0]==self.world.terrain.topology_revision:return cached[1]
        q=self.world.colonies[faction].queen
        cells=tuple(sorted({p for cell in q.footprint for p in neighbors(self.world.terrain,cell)}))
        self.home_cache[faction]=(self.world.terrain.topology_revision,cells)
        return cells

    def region_cost(self, key, seeds, position):
        if not seeds:
            return float('inf')
        field = self.field(key, seeds)
        index = position[1]*field.width+position[0]
        if field.distances[index] < 0 and field.frontier:
            self._expand_field(field)
        value = field.distances[index]
        return value if value >= 0 else (None if field.frontier else float('inf'))

    def station_cost(self,ant,station):
        field=self.fields.get(('goal',station.position))
        travel=distance(ant.position,station.position)
        if field is not None and field.valid(self.world.terrain):
            value=field.distances[ant.position[1]*field.width+ant.position[0]]
            if value>=0:travel=value
            elif not field.frontier:return float('inf')
        queen=self.world.colonies[ant.faction].queen
        home=min(distance(station.position,p) for p in queen.footprint)
        count=self.station_assignments[(ant.faction,station.id)]
        return travel+2*count+home*.2

    def step(self,ant,position,goal):
        self.metrics['route_queries']+=1;ant.navigation_status='ready'
        if position==goal:return position
        t=self.world.terrain
        if not (0<=goal[0]<t.capacity.shape[1] and 0<=goal[1]<t.capacity.shape[0]) or not t.capacity[goal[1],goal[0]]:
            ant.navigation_status='unreachable';return position
        # Short cached routes have only their actual static dependencies checked.
        if ant.route and ant.route_goal==goal and distance(position,ant.route[0])==1:
            changed=any(int(t.navigation_chunks[y,x])!=v for (x,y),v in ant.route_chunks.items())
            if not changed and t.capacity[ant.route[0][1],ant.route[0][0]]:
                self.metrics['route_hits']+=1;return ant.route[0]
            if all(t.capacity[y,x] for x,y in ant.route):
                self._stamp_route(ant);self.metrics['route_hits']+=1;return ant.route[0]
            self.metrics['route_invalidations']+=1
        ant.route=[];ant.route_goal=goal
        homes=self.home(ant.faction) if (ant.cargo or ant.state in ('return-report','return-soil')) else ()
        depot = self.world.depot_system.get(ant.depot_id, ant.faction) if ant.depot_id is not None else None
        honey = self.world.honeypots.get(ant.honeypot_id, ant.faction) if ant.honeypot_id is not None else None
        honey_cells = self.world.honeypots.cells(honey) if honey is not None else ()
        if honey is not None and ant.state == 'deliver-honeypot' and goal in honey_cells:
            key=('honeypot', honey.id);seeds=honey_cells
        elif ant.state == 'build-depot' and ant.construction_task is not None:
            construction = getattr(self.world, 'construction_system', None)
            job = construction.tasks.get(ant.construction_task) if construction is not None else None
            if job is None:
                return position
            key=('build', job.faction, job.target);seeds=construction.work_cells(job)
        elif depot is not None and goal in depot.footprint and ant.state == 'deliver-depot':
            key=('depot',depot.id);seeds=depot.footprint
        elif homes and goal in homes:
            key=('home',ant.faction);seeds=homes
        elif ant.state in ('central-expedition','frontier-explore'):
            key=('explore',ant.faction,ant.state);seeds=(goal,)
        elif goal in self.station_positions or distance(position,goal)>12:
            key=('goal',goal);seeds=(goal,)
        else:
            return self.local(ant,position,goal)
        field=self.field(key,seeds);i=position[1]*field.width+position[0]
        if field.distances[i]<0 and field.frontier:self._expand_field(field)
        value=field.distances[i]
        if value<0:
            ant.navigation_status='pending' if field.frontier else 'unreachable'
            self.metrics['wait_queries' if field.frontier else 'failed_routes']+=1
            return position
        if value==0:
            if key[0] in ('home', 'depot', 'honeypot', 'build'):ant.target=position
            return position
        options=[p for p in neighbors(t,position) if 0<=field.distances[p[1]*field.width+p[0]]<value]
        if not options:ant.navigation_status='pending';return position
        # Dynamic occupants affect only the immediate step, never global fields.
        return min(options,key=lambda p:(not t.available(*p),ant.trail_visits.get(p,0),p))

    def _stamp_route(self,ant):
        chunks=self.world.terrain.navigation_chunks
        ant.route_chunks={(x//16,y//16):int(chunks[y//16,x//16]) for x,y in ant.route}
        ant.route_revision=self.world.terrain.topology_revision

    def local(self,ant,position,goal):
        t=self.world.terrain;key=(position,goal);job=self.jobs.get(key)
        if job is None or job.revision!=t.topology_revision:
            if len(self.jobs)>=self.world.config.navigation_queue_limit:
                self.jobs.popitem(last=False);self.metrics['cancelled_jobs']+=1
            job=self.jobs[key]=LocalSearch(position,goal,t.topology_revision,self.turn)
            self.metrics['local_searches']+=1
        job.last_requested=self.turn
        used=job.expand(t,min(self.remaining,self.world.config.navigation_quantum),self.world.config.path_search_limit)
        self.remaining-=used;self.metrics['local_nodes']+=used
        if not job.done:
            ant.navigation_status='pending';self.metrics['wait_queries']+=1;return position
        self.jobs.pop(key,None)
        if not job.result:
            ant.navigation_status='unreachable';self.metrics['failed_routes']+=1;return position
        ant.route=job.result.copy();self._stamp_route(ant)
        return ant.route[0]

    def congestion_step(self,ant,position,goal):
        t=self.world.terrain
        available=[p for p in neighbors(t,position) if t.available(*p)]
        if not available:return position
        self.metrics['local_steering']+=1
        return min(available,key=lambda p:(distance(p,goal)+2*ant.trail_visits.get(p,0),p))

    def cache_bytes(self):
        return sum(len(f.distances)*f.distances.itemsize+len(f.frontier)*8+len(f.dependencies)*48 for f in self.fields.values())
