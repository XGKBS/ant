"""Mobile finite physical food buffers; local observation, no harvesting or combat actions."""
from ai.pathfinding import distance,neighbors,route_step
from simulation.spatial import SpatialIndex
from systems.perks import sensing


class Honeypots:
    def __init__(self,world):
        self.world=world;self.claims={};self.by_id={};self.index=SpatialIndex([])
        self.suppliers=SpatialIndex([])
        self.loaded=0;self.healed=0

    def begin_plan(self, index=None):
        self.by_id={a.id:a for a in self.world.ants if a.kind=='honeypot' and a.hp>0}
        self.index=index if index is not None else SpatialIndex(self.world.ants)
        self.suppliers=SpatialIndex(self.by_id.values())
        self.claims.clear()

    def get(self,ident,faction):
        ant=self.by_id.get(ident)
        return ant if ant is not None and ant.hp>0 and ant.faction==faction else None

    def cells(self,h):
        return tuple(sorted(neighbors(self.world.terrain,h.position)))

    def worker_target(self,ant):
        if (ant.kind!='worker' or not ant.cargo or ant.cargo_origin!='harvest'
                or not self.world.colonies[ant.faction].alive):
            return False
        homes=self.world.navigation.home(ant.faction)
        lower_home=min((distance(ant.position,p) for p in homes),default=float('inf'))
        candidates=[]
        for h in self.suppliers.near(ant.position,self.world.config.honeypot_follow_radius):
            if h.kind!='honeypot' or h.hp<=0 or h.faction!=ant.faction or h.stored_food+self.claims.get(h.id,0)>=10:
                continue
            cells=self.cells(h)
            if not cells or min(distance(ant.position,p) for p in cells)+2>=lower_home:
                continue
            cost=self.world.navigation.region_cost(('honeypot',h.id),cells,ant.position)
            if cost is not None and cost+2 < lower_home:
                candidates.append((cost,h.id,h,cells))
        if not candidates:
            # Optional buffer delivery never suspends a valid queen/depot route.
            return False
        _,ident,h,cells=min(candidates,key=lambda item:item[:2])
        ant.honeypot_id=ident;ant.state='deliver-honeypot'
        ant.target=ant.position if ant.position in cells else cells[0]
        self.claims[ident]=self.claims.get(ident,0)+min(ant.cargo,10-h.stored_food)
        return True

    def prepare(self,ant,combat):
        ant.dig_target=None;ant.combat_target=None
        colony=self.world.colonies[ant.faction]
        enemy=combat.enemy(ant,sensing(ant,colony)) if combat else None
        if enemy is not None:
            self.world.information.observe(ant,(),enemy,combat)
            cells=[ant.position]+list(neighbors(self.world.terrain,ant.position))
            ant.state='honeypot-retreat'
            ant.target=max(cells,key=lambda p:(combat.target_distance(p,enemy),p==ant.position or self.world.terrain.available(*p),-ant.visits.get(p,0),p)) if cells else ant.position
            return
        friends=[a for a in self.index.near(ant.position,self.world.config.honeypot_follow_radius)
                 if a.hp>0 and a.faction==ant.faction and a.kind!='honeypot']
        # Hold still to permit real loading by a nearby carrier.
        if ant.stored_food<10 and any(a.kind=='worker' and a.cargo and distance(a.position,ant.position)<=3 for a in friends):
            ant.state,ant.target='honeypot-hold',ant.position
            return
        if (not self.world.behavior.due(ant) and ant.target is not None
                and (ant.state!='honeypot-follow' or ant.escort_id in self.world.exploration.expedition_ids)
                and (ant.state!='honeypot-reposition' or ant.escort_target is not None
                     or any(distance(a.position,ant.target)<=1 for a in friends))):
            return
        leaders=[a for a in friends if a.id in self.world.exploration.expedition_ids]
        if leaders:
            leader=min(leaders,key=lambda a:(a.id!=ant.escort_id,distance(a.position,ant.position),a.id))
            ant.escort_id=leader.id
            ant.escort_target=leader.exploration_target or leader.position
            if distance(leader.position,ant.position)>3:
                cells=self.cells(leader)
                ant.state='honeypot-follow'
                ant.target=min(cells,key=lambda p:(distance(ant.position,p),p)) if cells else ant.position
                return
        nearby_suppliers=[h for h in self.suppliers.near(ant.position,self.world.config.honeypot_follow_radius)
                          if h.faction==ant.faction]
        underserved=[a for a in friends if distance(a.position,ant.position)>=7
                     and not any(h.id!=ant.id and h.faction==ant.faction and h.hp>0 and h.stored_food>0
                                 and distance(h.position,a.position)<=10 for h in nearby_suppliers)]
        if underserved:
            friend=min(underserved,key=lambda a:(a.id,distance(a.position,ant.position)))
            ant.state='honeypot-reposition';ant.target=friend.position
        elif ant.stored_food>0 and any(f.origin!=ant.id for f in self.world.information.latest(ant,('supply',))):
            needs=[f for f in self.world.information.latest(ant,('supply',))
                   if f.origin!=ant.id and f.payload and f.payload[0]<=1 and distance(ant.position,f.position)>3]
            if needs:
                need=min(needs,key=lambda f:(distance(ant.position,f.position),f.origin))
                ant.state,ant.target='honeypot-reposition',need.position
            else:
                ant.state,ant.target='honeypot-hold',ant.position
        elif not leaders and ant.escort_target is not None and distance(ant.position,ant.escort_target)>2:
            ant.state,ant.target='honeypot-reposition',ant.escort_target
        else:
            ant.state,ant.target='honeypot-hold',ant.position

    def step(self,ant,position):
        if ant.target is None or ant.target==position:
            return position
        desired=route_step(self.world,ant,position,ant.target)
        if desired!=position and not self.world.terrain.available(*desired):
            if ant.state=='honeypot-retreat':
                return position
            return self.world.navigation.congestion_step(ant,position,ant.target)
        return desired

    def action(self,ant,turn):
        if ant.hp<=0 or ant.action_used:
            return False
        if ant.kind=='honeypot':
            if not self.world.colonies[ant.faction].alive and ant.hp<ant.max_hp and ant.stored_food>0:
                amount=min(1,ant.max_hp-ant.hp,ant.stored_food)
                ant.stored_food-=amount;ant.hp+=amount
                self.world.food_system.eaten+=amount;self.healed+=amount
                ant.action_used,ant.last_action,ant.last_action_turn=True,'eat-stored',turn
                return True
            return False
        if ant.kind!='worker' or ant.state!='deliver-honeypot' or ant.cargo_origin!='harvest':
            return False
        h=self.get(ant.honeypot_id,ant.faction)
        if h is None or distance(ant.position,h.position)>1:
            return False
        amount=min(ant.cargo,10-h.stored_food)
        if amount<=0:
            return False
        h.stored_food+=amount;ant.cargo-=amount;self.loaded+=amount
        ant.action_used,ant.last_action,ant.last_action_turn=True,'load-honeypot',turn
        return True
