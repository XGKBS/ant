"""Bounded physical gossip, piggybacked on the existing order-communication pass."""
from dataclasses import dataclass
from collections import Counter
from ai.pathfinding import distance
from systems.perks import sensing


@dataclass(frozen=True)
class Fact:
    kind: str
    ident: object
    position: tuple
    payload: tuple
    observed: int
    origin: int
    expires: int

    @property
    def key(self):return self.kind,self.ident

    @property
    def version(self):return self.observed,self.origin


class Information:
    def __init__(self,world):
        self.world=world;self.metrics=Counter();self.last_turn=-1;self.index=None
        self.last_events=0

    def publish(self,ant,kind,ident,position,payload=()):
        turn=self.world.turn;key=(kind,ident);old=ant.information.get(key)
        if old is not None and old.expires>turn and old.position==position and old.payload==tuple(payload):return
        if old is not None and kind=='food' and payload and payload[0]>0 and turn-old.observed<4:return
        ttl=16 if kind in ('enemy','danger') else (32 if kind in ('excavation','supply') else 128)
        fact=Fact(kind,ident,position,tuple(payload),turn,ant.id,turn+ttl)
        self.accept(ant,fact);self.metrics['observed_'+kind]+=1

    def accept(self,ant,fact):
        key=fact.key;seen=ant.information_seen.get(key)
        if seen is not None and seen>=fact.version:return False
        ant.information_seen[key]=fact.version
        limit=self.world.config.information_capacity
        if len(ant.information_seen)>2*limit:
            del ant.information_seen[next(iter(ant.information_seen))]
        ant.information[key]=fact
        if len(ant.information)>limit:
            oldest=min(ant.information,key=lambda k:((0 if ant.information[k].expires<=self.world.turn else
                3 if ant.information[k].kind in ('enemy','danger') else 2 if ant.information[k].kind in ('food','supply') else 1),ant.information[k].observed,repr(k)))
            del ant.information[oldest]
        if fact.kind in ('enemy','danger') and self.world.colonies[ant.faction].alive:
            ant.pending_report=ant.pending_report or fact.position
        if fact.kind=='food':
            stock,tier,regenerates=fact.payload
            ant.food_observations[fact.ident]=(fact.position,stock,tier,fact.observed,regenerates)
            if stock>0 and fact.ident not in ant.ignored_food:ant.known_food[fact.ident]=fact.position
            elif stock<=0:ant.known_food.pop(fact.ident,None)
            while len(ant.known_food)>2*limit:ant.known_food.pop(next(iter(ant.known_food)))
            while len(ant.food_observations)>2*limit:ant.food_observations.pop(next(iter(ant.food_observations)))
        return True

    def observe(self,ant,visible,enemy=None,combat=None):
        for source in visible:
            regenerates=(hasattr(source,'next_refill') or source.tier not in ('trophy','drop')
                         and (source.tier!='micro' or self.world.config.micro_respawn_tier is not None))
            self.publish(ant,'food',source.id,source.position,(source.units,source.tier,regenerates))
        if enemy is not None and combat is not None:
            entity=combat.entities.get(enemy)
            if entity is not None:self.publish(ant,'enemy',enemy,entity.position,(entity.faction,))
        if ant.foreign_target is not None and self.world.config.combat_enabled:
            self.publish(ant,'danger',ant.foreign_target,ant.foreign_target)
        if (ant.id+self.world.turn)%self.world.config.idle_planning_interval==0:
            if ant.moved_this_turn and self.world.terrain.traffic[ant.position[1],ant.position[0]]>=self.world.config.busy_path_visits:
                self.publish(ant,'route',ant.position,ant.position,(int(self.world.terrain.capacity[ant.position[1],ant.position[0]]),))
            if ant.kind!='honeypot' and not ant.cargo and self.world.turn%100>=90:
                self.publish(ant,'supply',ant.id,ant.position,(1,))
            if ant.kind=='honeypot' and ant.stored_food<2:self.publish(ant,'supply',ant.id,ant.position,(10-ant.stored_food,))

    def near(self,ant,radius,limit=16):
        if self.index is None:return ()
        return self.index.near_limited(ant.position,radius,limit,(self.world.turn//self.world.config.idle_planning_interval)*13+ant.id)

    def propagate(self,turn,index):
        if turn<=self.last_turn:return
        self.last_turn=turn;self.index=index;self.last_events=0
        w=self.world;c=w.config;deliveries=[];ants=w.ants
        # Read snapshots until all intents are collected. No same-turn chain flooding.
        start=(turn*31)%len(ants) if ants else 0
        for ant in ants[start:]+ants[:start]:
            if ant.hp<=0 or (ant.id+turn)%c.information_interval:continue
            expired=[key for key,fact in ant.information.items() if fact.expires<=turn]
            for key in expired:
                fact=ant.information.pop(key)
                if fact.kind=='food' and ant.food_observations.get(fact.ident,())[3:4]==(fact.observed,):
                    ant.known_food.pop(fact.ident,None);ant.food_observations.pop(fact.ident,None)
            if not ant.information:continue
            peers=[a for a in index.near_limited(ant.position,c.communication_radius,c.information_probe_limit,(turn//c.information_interval)*13+ant.id)
                   if a.faction==ant.faction and a.id!=ant.id]
            peers.sort(key=lambda a:(distance(a.position,ant.position),a.id))
            if not peers:continue
            # Rotate through a bounded memory so food does not starve other categories.
            facts=list(ant.information.values());offset=(turn//c.information_interval+ant.id)%len(facts)
            sent=0
            for fact in facts[offset:]+facts[:offset]:
                if fact.expires<=turn:continue
                for peer in peers[:c.information_peers]:
                    self.metrics['comparisons']+=1
                    known=peer.information.get(fact.key)
                    if known is not None and known.expires>turn and known.position==fact.position and known.payload==fact.payload:
                        continue  # content digest agrees; no redundant broadcast/version churn
                    if peer.information_seen.get(fact.key,(-1,-1))<fact.version:
                        deliveries.append((peer,ant,fact));sent+=1
                        if sent>=c.information_messages_per_ant:break
                if sent>=c.information_messages_per_ant:break
            if len(deliveries)>=c.information_events_per_turn:break
        # Stable rotating priority prevents a low-ID population monopolizing a busy queue.
        if deliveries:
            start=turn%len(deliveries);deliveries=deliveries[start:]+deliveries[:start]
        for peer,sender,fact in deliveries[:c.information_events_per_turn]:
            if self.accept(peer,fact):
                self.metrics['relayed_'+fact.kind]+=1;self.metrics['received']+=1
                self.last_events+=1;peer.last_information_turn=sender.last_information_turn=turn
        self.metrics['events_peak']=max(self.metrics['events_peak'],self.last_events)

    def latest(self,ant,kinds):
        return (f for f in ant.information.values() if f.kind in kinds and f.expires>self.world.turn)
