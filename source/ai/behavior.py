"""Cheap committed local patrols, useful idle waypoints and activity diagnostics."""
from collections import Counter
from ai.pathfinding import distance,neighbors
from simulation.terrain import SOIL


class Behavior:
    def __init__(self,world):
        self.world=world;self.guard_ids=set();self.guard_slots={};self.excavation_claims=set();self.assignments=0;self.retries=0;self.metrics=Counter()

    def begin_plan(self):
        self.assignments=self.retries=0;self.guard_ids.clear();self.guard_slots.clear();self.excavation_claims.clear()
        for faction in range(4):
            soldiers=[a for a in self.world.ants if a.faction==faction and a.kind=='soldier' and a.hp>0]
            guards=soldiers[:min(4,len(soldiers)//4)]
            self.guard_ids.update(a.id for a in guards)
            self.guard_slots.update((a.id,i) for i,a in enumerate(guards))

    def due(self,ant):
        c=self.world.config
        interval=c.idle_planning_interval*(2 if len(self.world.ants)>=c.idle_population_threshold else 1)
        return (ant.id+self.world.turn)%interval==0

    def prepare(self,ant,soldier=False):
        w=self.world;c=w.config
        if ant.cargo and not soldier or ant.soil_cargo or ant.construction_task is not None:return False
        if soldier and ant.information:
            warnings=[f for f in w.information.latest(ant,('enemy','danger')) if distance(ant.position,f.position)<=16]
            if warnings:
                fact=max(warnings,key=lambda f:(f.observed,repr(f.key)))
                if ant.position!=fact.position:
                    ant.state,ant.target='investigate',fact.position;ant.idle_target=None
                    return True
                ant.information.pop(fact.key,None)  # checked the last-known position, no omniscient chase
        if ant.idle_target is not None:
            x,y=ant.idle_target
            if (w.turn<ant.idle_until and w.terrain.capacity[y,x] and (ant.blocked_turns<8 or ant.position==ant.idle_target)):
                ant.state,ant.target=ant.idle_role,ant.idle_target
                if ant.position==ant.target and ant.state!='guard':ant.state='patrol-hold'
                return True
        if (not self.due(ant) and ant.idle_until>0) or self.assignments>=c.idle_assignments_per_turn:
            ant.state,ant.target='planning-wait',ant.position
            return True
        self.assignments+=1;self.metrics['assignments']+=1
        information=w.information
        sightings=list(information.latest(ant,('enemy','danger')))
        if soldier and sightings:
            fact=max(sightings,key=lambda f:(f.observed,-distance(ant.position,f.position),repr(f.key)))
            if distance(ant.position,fact.position)<=16:
                ant.state,ant.target='investigate',fact.position
                ant.idle_target=None
                return True
        if soldier and ant.id in self.guard_ids and w.colonies[ant.faction].alive:
            queen=w.colonies[ant.faction].queen.position;slot=self.guard_slots[ant.id]
            offsets=((-3,0),(4,0),(0,-3),(0,4));dx,dy=offsets[slot%4]
            goal=(max(0,min(c.size-1,queen[0]+dx)),max(0,min(c.size-1,queen[1]+dy)))
            if w.terrain.capacity[goal[1],goal[0]]:
                ant.idle_role='guard';ant.idle_target=goal;ant.idle_until=w.turn+32
                ant.state,ant.target=ant.idle_role,goal;return True
        # Escort locally observed working ants; only one in four patrol IDs seeks this role.
        friends=list(information.near(ant,6,16)) if soldier and ant.id%4==1 else []
        carriers=[a for a in friends if a.faction==ant.faction and a.kind=='worker' and a.cargo]
        if carriers:
            worker=min(carriers,key=lambda a:(distance(a.position,ant.position),a.id))
            if distance(worker.position,ant.position)<=2:
                ant.idle_role='guard';goal=ant.position
            else:
                ant.idle_role='escort';goal=worker.position
        else:
            # Eight compass candidates, rotated by stable ID; bounded local geography only.
            offsets=((6,0),(4,4),(0,6),(-4,4),(-6,0),(-4,-4),(0,-6),(4,-4))
            candidates=[]
            for slot in range(8):
                dx,dy=offsets[(slot+ant.id)%8];p=(ant.position[0]+dx,ant.position[1]+dy)
                if not (0<=p[0]<c.size and 0<=p[1]<c.size and w.terrain.capacity[p[1],p[0]]):continue
                if any(distance(p,f.position)<=2 for f in sightings):continue
                candidates.append((ant.visits.get(p,0),slot,p))
            if not candidates:
                ant.state,ant.target='patrol-hold' if soldier else 'idle-wait',ant.position;return True
            goal=min(candidates)[2];ant.idle_role='patrol-route' if soldier else 'frontier-local'
        ant.idle_target,ant.idle_until=goal,w.turn+12
        ant.state,ant.target=ant.idle_role,goal
        return True

    def step(self,ant,position):
        if ant.target==position or ant.target is None:return position
        t=self.world.terrain;options=[p for p in neighbors(t,position) if t.available(*p)]
        closer=[p for p in options if distance(p,ant.target)<distance(position,ant.target)]
        if closer:return min(closer,key=lambda p:(ant.visits.get(p,0),distance(p,ant.target),p))
        if self.retries<self.world.config.idle_path_retries_per_turn and self.due(ant):
            self.retries+=1
            return self.world.navigation.step(ant,position,ant.target)
        return position

    def record(self,ant,turn):
        if not ant.moved_this_turn:ant.stationary_turns+=1
        if ant.moved_this_turn or ant.last_action_turn==turn or ant.last_information_turn==turn:activity='productive'
        elif ant.state in ('guard','patrol-hold','honeypot-hold'):activity='strategic_stationary'
        elif ant.navigation_status=='pending' or 'plan' in ant.state or ant.state in ('build-depot','move-stone','compose-stone','gather','idle-wait','deliver-honeypot'):activity='waiting_dependency'
        elif ant.target is not None:activity='temporarily_blocked'
        else:activity='unproductive_idle'
        ant.activity=activity
        if activity=='unproductive_idle':ant.unproductive_idle_turns+=1
        self.metrics[activity]+=1
