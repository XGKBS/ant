"""No injected population or reserves: a generated game with normal rules."""
import argparse
import json
from time import perf_counter
import numpy as np
from config import Config
from simulation.engine import Engine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--size', type=int, default=64)
    parser.add_argument('--turns', type=int, default=300)
    args = parser.parse_args()
    engine = Engine(Config(size=args.size))
    start = perf_counter()
    for i in range(args.turns):
        engine.advance(1)
        assert np.all(engine.world.terrain.occupancy <= engine.world.terrain.capacity)
        if engine.ended or (i+1) % 50 == 0 or i+1 == args.turns:
            print(json.dumps({'turn': engine.turn, 'ants': len(engine.world.ants), 'soldiers': sum(a.kind == 'soldier' for a in engine.world.ants),
                              'queen_hp': [c.queen.hp for c in engine.world.colonies], 'upgrades': [c.upgraded for c in engine.world.colonies],
                              'births': [c.produced_workers+c.produced_soldiers for c in engine.world.colonies], 'reserves': [c.reserves for c in engine.world.colonies],
                              'attacks': engine.combat.attacks, 'elapsed_seconds': round(perf_counter()-start, 3), 'outcome': engine.outcome}), flush=True)
        if engine.ended:
            break

if __name__ == '__main__':
    main()
