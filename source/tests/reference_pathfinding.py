"""Frozen Phase 3 search oracle for exact differential tests, not production code."""
from heapq import heappush, heappop

def distance(a, b):
    return abs(a[0]-b[0])+abs(a[1]-b[1])

def neighbors(terrain, p):
    x, y = p
    h, w = terrain.capacity.shape
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        q = x+dx, y+dy
        if 0 <= q[0] < w and 0 <= q[1] < h and terrain.capacity[q[1], q[0]]:
            yield q

def reference_search(terrain, start, goal, limit=4096, avoid=frozenset()):
    if start == goal:
        return []
    frontier = [(distance(start, goal), 0, start)]
    costs, parents = {start: 0}, {}
    expanded = 0
    while frontier and expanded < limit:
        _, negative_cost, p = heappop(frontier)
        cost = -negative_cost
        if cost != costs[p]:
            continue
        if p == goal:
            route = []
            while p != start:
                route.append(p)
                p = parents[p]
            return route[::-1]
        expanded += 1
        for q in neighbors(terrain, p):
            if q in avoid:
                continue
            x, y = q
            crowded = terrain.occupancy[y, x] >= terrain.capacity[y, x]
            new_cost = cost+1+(3 if crowded else 0)
            if new_cost < costs.get(q, float('inf')):
                costs[q], parents[q] = new_cost, p
                heappush(frontier, (new_cost+distance(q, goal), -new_cost, q))
    return []
