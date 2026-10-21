"""Explicit population fixtures; these are not claims of naturally grown populations."""
import argparse
import json
import platform
from time import perf_counter
import numpy as np
from config import Config
from entities.models import Ant
from simulation.engine import Engine

def populated(count, scenario, size=512):
    engine = Engine(Config(size=size))
    world = engine.world
    world.ants.clear()
    world.terrain.occupancy[:] = 0
    candidates = list(world.food_candidates)
    if scenario == 'contact':
        # A two-cell lattice near the center supplies legal space and nearby opponents.
        candidates = [p for p in candidates if p[0] % 2 == 0 and p[1] % 2 == 0]
        candidates.sort(key=lambda p: ((p[0]-size/2)**2+(p[1]-size/2)**2, p))
    if len(candidates) < count:
        raise ValueError('Not enough legal benchmark cells')
    for i, p in enumerate(candidates[:count]):
        kind = 'soldier' if (i//4) % 4 == 0 else 'worker'
        world.ants.append(Ant(world.allocate_id(), i % 4, p, kind=kind))
        world.terrain.occupancy[p[1], p[0]] += 1
    for colony in world.colonies:
        colony.upgraded = True
        colony.reserves = 40
    engine._plan()
    return engine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--turns', type=int, default=20)
    parser.add_argument('--counts', type=int, nargs='+', default=[100, 500, 1000])
    parser.add_argument('--scenarios', nargs='+', choices=['distributed', 'contact'], default=['distributed', 'contact'])
    args = parser.parse_args()
    print(json.dumps({'platform': platform.platform(), 'cpu': platform.processor(), 'python': platform.python_version(), 'numpy': np.__version__, 'map_size': 512, 'seed': 7, 'turns_requested': args.turns}), flush=True)
    for scenario in args.scenarios:
        for count in args.counts:
            start = perf_counter()
            engine = populated(count, scenario)
            setup = perf_counter()-start
            durations, populations = [], []
            for _ in range(args.turns):
                if engine.ended:
                    break
                start = perf_counter()
                engine.advance(1)
                t = engine.world.terrain
                assert np.all(t.occupancy <= t.capacity)
                durations.append(perf_counter()-start)
                populations.append(len(engine.world.ants))
            print(json.dumps({'scenario': scenario, 'initial_ants': count, 'final_ants': len(engine.world.ants), 'population_min': min(populations), 'population_max': max(populations), 'turns': engine.turn,
                              'setup_seconds': round(setup, 4), 'simulation_seconds': round(sum(durations), 4), 'mean_ms_per_turn': round(1000*sum(durations)/len(durations), 3), 'max_ms_per_turn': round(1000*max(durations), 3),
                              'attacks': engine.combat.attacks, 'ant_deaths': engine.lifecycle.ant_deaths, 'births': sum(c.produced_workers+c.produced_soldiers for c in engine.world.colonies),
                              'queenless': sum(not c.alive for c in engine.world.colonies), 'ended': engine.ended}), flush=True)

if __name__ == '__main__':
    main()
