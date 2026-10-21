"""Bounded A*, with transient occupancy costs and per-worker route caching."""
from heapq import heappush, heappop
from array import array

DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))

def distance(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def neighbors(terrain, position):
    x, y = position
    h, w = terrain.capacity.shape
    for dx, dy in DIRECTIONS:
        p = x+dx, y+dy
        if 0 <= p[0] < w and 0 <= p[1] < h and terrain.capacity[p[1], p[0]]:
            yield p

class SearchWorkspace:
    """Reusable integer storage; generations avoid clearing a whole map per search."""
    def __init__(self, terrain):
        self.height, self.width = terrain.capacity.shape
        count = self.height*self.width
        self.costs = array('i', [0])*count
        self.parents = array('i', [0])*count
        self.stamps = array('Q', [0])*count
        self.generation = 0
        self.searches = 0
        self.expanded = 0

    def begin(self):
        self.generation += 1
        if self.generation >= 2**64:
            self.stamps = array('Q', [0])*len(self.stamps)
            self.generation = 1
        self.searches += 1
        return self.generation

def find_path(terrain, start, goal, limit=4096, avoid=frozenset()):
    """Same bounded A* order as Phase 3; flat buffers avoid NumPy scalar/tuple churn."""
    if start == goal:
        return []
    h, w = terrain.capacity.shape
    sx, sy = start
    gx, gy = goal
    if not (0 <= sx < w and 0 <= sy < h and 0 <= gx < w and 0 <= gy < h):
        return []
    workspace = getattr(terrain, '_search_workspace', None)
    if workspace is None or (workspace.height, workspace.width) != (h, w):
        workspace = terrain._search_workspace = SearchWorkspace(terrain)
    generation = workspace.begin()
    costs, parents, stamps = workspace.costs, workspace.parents, workspace.stamps
    capacity = memoryview(terrain.capacity).cast('B')
    occupancy = memoryview(terrain.occupancy).cast('B')
    origin, destination = sy*w+sx, gy*w+gx
    costs[origin], stamps[origin] = 0, generation
    # x*h+y has exactly the lexicographic order of the old (x,y) heap tie breaker.
    frontier = [(abs(sx-gx)+abs(sy-gy), 0, sx*h+sy)]
    blocked = {y*w+x for x, y in avoid if 0 <= x < w and 0 <= y < h}
    infinity = 2**31-1
    expanded = 0
    while frontier and expanded < limit:
        _, negative_cost, tie = heappop(frontier)
        x, y = divmod(tie, h)
        p = y*w+x
        cost = -negative_cost
        if stamps[p] != generation or cost != costs[p]:
            continue
        if p == destination:
            route = []
            while p != origin:
                cy, cx = divmod(p, w)
                route.append((cx, cy))
                p = parents[p]
            workspace.expanded += expanded
            return route[::-1]
        expanded += 1
        for dx, dy in DIRECTIONS:
            qx, qy = x+dx, y+dy
            if not (0 <= qx < w and 0 <= qy < h):
                continue
            q = qy*w+qx
            cap = capacity[q]
            if not cap or q in blocked:
                continue
            new_cost = cost + 1 + (3 if occupancy[q] >= cap else 0)
            previous = costs[q] if stamps[q] == generation else infinity
            if new_cost < previous:
                costs[q], parents[q], stamps[q] = new_cost, p, generation
                heappush(frontier, (new_cost+abs(qx-gx)+abs(qy-gy), -new_cost, qx*h+qy))
    workspace.expanded += expanded
    return []

def route_step(world, ant, position, goal):
    navigation = getattr(world,'navigation',None)
    if navigation is not None:
        return navigation.step(ant,position,goal)
    t = world.terrain
    if goal == position:
        return position
    if ant.route_goal != goal or ant.route_revision != t.revision or not ant.route or distance(position, ant.route[0]) != 1:
        ant.route = find_path(t, position, goal, world.config.path_search_limit)
        ant.route_goal, ant.route_revision = goal, t.revision
    return ant.route[0] if ant.route else position
