"""Sparse terrain frontiers and at most two shared expedition routes per faction."""
from math import ceil
from ai.pathfinding import distance


class Exploration:
    def __init__(self, world):
        self.world=world
        self.seen=[set() for _ in world.colonies]
        self.frontiers=[set() for _ in world.colonies]
        self.expedition_ids=set();self.roles={};self.claims={};self.failed={};self.routes={}

    def waypoint(self,chunk):
        w=self.world;s=w.config.exploration_chunk
        x0,y0=chunk[0]*s,chunk[1]*s
        center=(min(w.config.size-1,x0+s//2),min(w.config.size-1,y0+s//2))
        cells=((x,y) for y in range(y0,min(w.config.size,y0+s)) for x in range(x0,min(w.config.size,x0+s)))
        return next((p for p in sorted(cells,key=lambda p:(distance(p,center),p)) if w.terrain.capacity[p[1],p[0]]),None)

    def begin_plan(self):
        w=self.world;c=w.config;s=c.exploration_chunk;n=(c.size+s-1)//s
        old_roles=self.roles.copy();self.expedition_ids.clear();self.roles.clear();self.claims.clear()
        new_assignments=0
        self.failed={key:until for key,until in self.failed.items() if until>w.turn}
        workers=[[] for _ in w.colonies]
        for ant in w.ants:
            if ant.hp<=0:continue
            chunk=(ant.position[0]//s,ant.position[1]//s)
            ant.surveyed_chunks.add(chunk)
            seen,frontier=self.seen[ant.faction],self.frontiers[ant.faction]
            if chunk not in seen:
                seen.add(chunk);frontier.discard(chunk);x,y=chunk
                for q in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if 0<=q[0]<n and 0<=q[1]<n and q not in seen:frontier.add(q)
            if ant.kind=='worker':workers[ant.faction].append(ant)
        if not c.exploration_enabled or w.turn<c.exploration_start_turn:return
        groups={}
        for colony,members in zip(w.colonies,workers):
            if not colony.alive or colony.threat in ('near-base','critical') or colony.strategic_state=='Total War':continue
            members.sort(key=lambda a:(not (a.id in old_roles and a.exploration_until>w.turn),-a.id))
            number=min(max(0,len(members)-1),ceil(len(members)*c.expedition_fraction))
            for slot,ant in enumerate(members[:number]):
                if ant.id not in old_roles:
                    if new_assignments>=c.idle_assignments_per_turn:continue
                    new_assignments+=1
                if ant.order_state=='Total War':continue
                state=(old_roles[ant.id][0] if ant.id in old_roles and ant.exploration_until>w.turn
                       else 'central-expedition' if slot%2==0 else 'frontier-explore')
                self.expedition_ids.add(ant.id);self.roles[ant.id]=(state,slot)
                groups.setdefault((ant.faction,state),[]).append(ant)
        for key,members in groups.items():
            faction,state=key;old=self.routes.get(key)
            if old is not None:
                goal,until=old;chunk=(goal[0]//s,goal[1]//s)
                if (w.turn<until and w.terrain.capacity[goal[1],goal[0]] and (faction,chunk) not in self.failed
                        and not any(distance(a.position,goal)<=1 for a in members)):
                    self.claims[(faction,chunk)]=self.claims.get((faction,chunk),0)+1
                    continue
            if old is not None and (w.turn+faction)%c.idle_planning_interval:
                continue  # stagger nonurgent shared frontier selection
            center=(max(0,min(n-1,n//2+(-1 if faction%2==0 else 1))),
                    max(0,min(n-1,n//2+(-1 if faction<2 else 1))))
            leader=min(members,key=lambda a:(abs(a.position[0]//s-center[0])+abs(a.position[1]//s-center[1]),a.id))
            current=(leader.position[0]//s,leader.position[1]//s)
            chunks=[]
            if state=='central-expedition':
                chunks.append(tuple(current[i]+(1 if center[i]>current[i] else -1 if center[i]<current[i] else 0) for i in (0,1)))
            # Faction coverage is observational only. Choose from the leader's own
            # local geographic frontier, not another ant's uncommunicated discoveries.
            cx,cy=current
            local=[p for p in ((cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1))
                   if 0<=p[0]<n and 0<=p[1]<n]
            chunks+=sorted(local,key=lambda p:(p in leader.surveyed_chunks,
                            self.claims.get((faction,p),0)*4+abs(p[0]-center[0])+abs(p[1]-center[1]),p))
            goal=None
            for chunk in chunks:
                if (faction,chunk) in self.failed:continue
                candidate=self.waypoint(chunk)
                if candidate is not None and all(distance(a.position,candidate)>1 for a in members):
                    goal=candidate;self.claims[(faction,chunk)]=self.claims.get((faction,chunk),0)+1;break
            if goal is not None:self.routes[key]=(goal,w.turn+c.exploration_commit_turns)
            else:self.routes.pop(key,None)

    def prepare(self,ant):
        if ant.id not in self.roles or ant.cargo or ant.soil_cargo or ant.construction_task is not None:return False
        # Legitimately received ordinary food discoveries take priority over new surveying.
        if any(ident not in self.world.navigation.station_ids and ident not in ant.ignored_food for ident in ant.known_food):return False
        # Public station orbits do not trap every expedition.
        radius=3 if self.world.colonies[ant.faction].active_perk=='sensitivity' else 2
        if any(f.units>0 and distance(ant.position,f.position)<=radius for f in self.world.food):return False
        if (self.world.food_system.sample(ant.position)>0
                and not any(distance(ant.position,station.position)<=station.max_scent for station in self.world.stations)):
            ant.state,ant.target='scout-scent',None
            return True
        state,slot=self.roles[ant.id];route=self.routes.get((ant.faction,state))
        if route is None:return False
        ant.exploration_target,ant.exploration_until=route
        ant.state,ant.target=state,ant.exploration_target;ant.food_id=None
        return True

    def failure(self,ant):
        if ant.exploration_target is not None:
            s=self.world.config.exploration_chunk
            chunk=(ant.exploration_target[0]//s,ant.exploration_target[1]//s)
            self.failed[(ant.faction,chunk)]=self.world.turn+self.world.config.failed_target_cooldown
            ant.exploration_target=None;ant.exploration_until=0
