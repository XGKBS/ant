"""Run from D:\\Codex: .venv\\Scripts\\python.exe -m benchmarks.phase2."""
import argparse
import json
import platform
from time import perf_counter
import numpy as np
from config import Config
from simulation.engine import Engine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--turns', type=int, default=1000)
    args = parser.parse_args()
    print(json.dumps({'platform': platform.platform(), 'cpu': platform.processor(), 'python': platform.python_version(), 'numpy': np.__version__}))
    for size in (64, 128, 512):
        start = perf_counter()
        engine = Engine(Config(size=size))
        build_seconds = perf_counter()-start
        start = perf_counter()
        for _ in range(args.turns):
            engine.advance(1)
            assert np.all(engine.world.terrain.occupancy <= engine.world.terrain.capacity)
        elapsed = perf_counter()-start
        print(json.dumps({'size': size, 'ants': len(engine.world.ants), 'turns': engine.turn, 'build_seconds': round(build_seconds, 4), 'simulation_seconds': round(elapsed, 4), 'ms_per_turn': round(1000*elapsed/args.turns, 3), 'reserves': [c.reserves for c in engine.world.colonies], 'harvested': engine.food.harvested, 'delivered': engine.food.delivered, 'dug': engine.world.terrain.excavated_units, 'food_sites': len(engine.world.food), 'queued_spawns': len(engine.food.pending)}), flush=True)

if __name__ == '__main__':
    main()
