"""Public permanent sites; placement consumes no random numbers or terrain."""
from entities.models import SupplyStation
from ai.pathfinding import distance, find_path

OFFSETS = (((5,0),(0,5),(5,5)), ((-5,0),(0,5),(-5,5)),
           ((0,-5),(5,0),(5,-5)), ((0,-5),(-5,0),(-5,-5)))

def create_stations(world):
    stations = []
    t = world.terrain
    occupied = {p for c in world.colonies for p in c.queen.footprint}
    for colony, offsets in zip(world.colonies, OFFSETS):
        anchor = colony.queen.position
        start = next(a.position for a in world.ants if a.faction == colony.faction)
        for dx, dy in offsets:
            intended = (anchor[0]+dx, anchor[1]+dy)
            def valid(p):
                return (0 <= p[0] < world.config.size and 0 <= p[1] < world.config.size
                        and t.capacity[p[1],p[0]] and p not in occupied)
            def reachable(p):
                return p == start or bool(find_path(t, start, p, world.config.path_search_limit))
            p = intended
            reason = 'exact offset'
            if not valid(p) or not reachable(p):
                if not (0 <= p[0] < world.config.size and 0 <= p[1] < world.config.size):
                    reason = f'intended {intended} outside map'
                elif p in occupied:
                    reason = f'intended {intended} conflicts with queen or station'
                elif not t.capacity[p[1],p[0]]:
                    reason = f'intended {intended} is impassable terrain'
                else:
                    reason = f'intended {intended} has no route within the existing search budget'
                def score(q):
                    wrong = sum(1 for a,b in zip((q[0]-anchor[0],q[1]-anchor[1]),(dx,dy)) if b and a*b <= 0)
                    angular = abs(dx*(q[1]-anchor[1])-dy*(q[0]-anchor[0]))
                    return distance(q,intended), wrong, angular, q
                candidates = sorted((q for q in world.food_candidates if valid(q)), key=score)
                p = next((q for q in candidates if reachable(q)), None)
                if p is None:
                    raise ValueError(f'No reachable supply placement for colony {colony.faction}: {intended}')
                reason += f'; nearest reachable fallback {p}'
            occupied.add(p)
            stations.append(SupplyStation(world.allocate_id(),p,'supply',5,4,
                                          origin_faction=colony.faction,intended=intended,placement_reason=reason))
    return stations

class Supply:
    def __init__(self, world):
        self.world = world
        self.initial_units = sum(s.units for s in world.stations)
        self.generated_units = 0
        self.last_refill_units = 0
        self.last_refill_turn = 0

    def tick(self, turn):
        generated = 0
        for s in self.world.stations:
            if turn >= s.next_refill:
                periods = (turn-s.next_refill)//25+1
                amount = 5*periods
                s.units += amount
                s.generated_units += amount
                s.last_refill_units = amount
                s.next_refill += 25*periods
                generated += amount
        if generated:
            self.generated_units += generated
            self.last_refill_units, self.last_refill_turn = generated, turn
