"""Phase 3's exact fixtures/timed window, plus untimed deterministic state fingerprints."""
import argparse
import cProfile
import dataclasses
import hashlib
import json
import platform
import pstats
from pathlib import Path
from time import perf_counter
import numpy as np
from benchmarks.phase3 import populated

def canonical(value):
    if dataclasses.is_dataclass(value):
        return {f.name: canonical(getattr(value, f.name)) for f in dataclasses.fields(value)
                if f.name not in ('route_revision',)}
    if isinstance(value, dict):
        return sorted([(canonical(k), canonical(v)) for k, v in value.items()], key=repr)
    if isinstance(value, (set, frozenset)):
        return sorted([canonical(v) for v in value], key=repr)
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value

def fingerprint(engine):
    world = engine.world
    digest = hashlib.sha256()
    for array in (world.terrain.cells, world.terrain.capacity, world.terrain.occupancy,
                  world.terrain.traffic, engine.pheromones.values):
        digest.update(array.tobytes())
    state = [engine.turn, engine.progress, engine.ended, engine.outcome, engine.winner,
             world.ants, world.colonies, world.food, world.rng.getstate(), world.next_food_id,
             world.terrain.excavated_units, engine.combat.attacks, engine.lifecycle.ant_deaths,
             engine.food.harvested, engine.food.delivered, engine.food.eaten,
             engine.food.discarded, engine.food.trophy_created, engine.food.generated, engine.food.pending]
    digest.update(json.dumps(canonical(state), separators=(',', ':')).encode())
    return digest.hexdigest()

def instrument_searches():
    import ai.pathfinding as paths
    import ai.state_machine as states
    counters = {'searches': 0, 'failed_searches': 0, 'route_calls': 0, 'global_revision_only': 0}
    original_search, original_route = paths.find_path, paths.route_step
    def search(*args, **kwargs):
        counters['searches'] += 1
        result = original_search(*args, **kwargs)
        if not result:
            counters['failed_searches'] += 1
        return result
    def route(world, ant, position, goal):
        counters['route_calls'] += 1
        if position != goal and ant.route and ant.route_goal == goal and paths.distance(position, ant.route[0]) == 1 and ant.route_revision != world.terrain.revision:
            counters['global_revision_only'] += 1
        return original_route(world, ant, position, goal)
    paths.find_path = states.find_path = search
    paths.route_step = states.route_step = route
    return counters

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--turns', type=int, default=20)
    parser.add_argument('--counts', type=int, nargs='+', default=[100, 500, 1000])
    parser.add_argument('--scenarios', nargs='+', choices=['distributed', 'contact'], default=['distributed', 'contact'])
    parser.add_argument('--profile', action='store_true')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = instrument_searches() if args.profile else None
    with args.output.open('w', encoding='utf-8') as out:
        header = dict(platform=platform.platform(), cpu=platform.processor(), python=platform.python_version(),
                      numpy=np.__version__, map_size=512, seed=7, turns_requested=args.turns, profiled=args.profile)
        out.write(json.dumps(header)+'\n')
        print(json.dumps(header), flush=True)
        for scenario in args.scenarios:
            for count in args.counts:
                if diagnostics:
                    for key in diagnostics:
                        diagnostics[key] = 0
                start = perf_counter()
                engine = populated(count, scenario)
                setup = perf_counter()-start
                durations, populations, hashes = [], [], [fingerprint(engine)]
                profiler = cProfile.Profile() if args.profile else None
                for _ in range(args.turns):
                    if engine.ended:
                        break
                    if profiler:
                        profiler.enable()
                    start = perf_counter()
                    engine.advance(1)
                    terrain = engine.world.terrain
                    assert np.all(terrain.occupancy <= terrain.capacity)
                    durations.append(perf_counter()-start)
                    if profiler:
                        profiler.disable()
                    populations.append(len(engine.world.ants))
                    hashes.append(fingerprint(engine))
                record = dict(scenario=scenario, initial_ants=count, final_ants=len(engine.world.ants),
                              population_min=min(populations), population_max=max(populations), populations=populations,
                              turns=engine.turn, setup_seconds=round(setup, 4), simulation_seconds=round(sum(durations), 4),
                              mean_ms_per_turn=round(1000*sum(durations)/len(durations), 3),
                              max_ms_per_turn=round(1000*max(durations), 3), turn_ms=[round(t*1000, 6) for t in durations],
                              attacks=engine.combat.attacks, ant_deaths=engine.lifecycle.ant_deaths,
                              births=sum(c.produced_workers+c.produced_soldiers for c in engine.world.colonies),
                              queenless=sum(not c.alive for c in engine.world.colonies), ended=engine.ended, fingerprints=hashes)
                workspace = getattr(engine.world.terrain, '_search_workspace', None)
                if workspace is not None:
                    record['search_requests'] = getattr(workspace, 'requests', workspace.searches)
                    record['executed_searches'] = workspace.searches
                    record['cached_searches'] = getattr(workspace, 'cache_hits', 0)
                    record['expanded_nodes'] = workspace.expanded
                if profiler:
                    stem = args.output.parent/f'{args.output.stem}_{scenario}_{count}'
                    profiler.dump_stats(str(stem)+'.prof')
                    with Path(str(stem)+'.txt').open('w', encoding='utf-8') as report:
                        pstats.Stats(profiler, stream=report).strip_dirs().sort_stats('cumulative').print_stats(45)
                        pstats.Stats(profiler, stream=report).strip_dirs().sort_stats('tottime').print_stats(25)
                    record['search_diagnostics'] = dict(diagnostics)
                out.write(json.dumps(record)+'\n')
                out.flush()
                print(json.dumps({k: v for k, v in record.items() if k not in ('fingerprints', 'turn_ms', 'populations')}), flush=True)

if __name__ == '__main__':
    main()
