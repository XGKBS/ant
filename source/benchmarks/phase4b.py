"""Same Phase 3/4A fixtures and timed window; construction audits are untimed."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
from time import perf_counter
import numpy as np
from benchmarks.phase3 import populated
from benchmarks.phase4a import canonical, fingerprint


def full_fingerprint(e):
    c, t = e.construction, e.world.terrain
    h = hashlib.sha256(fingerprint(e).encode())
    h.update(t.layers.tobytes())
    h.update(t.stone_ids.tobytes())
    jobs = [(j.id, j.faction, j.kind, j.target, j.stones, j.direction, j.crew,
             (j.progress.numerator, j.progress.denominator), j.soil, j.created) for j in c.tasks.values()]
    state = [t.loose_soil, list(c.stones.groups.values()), jobs, c.completed, c.cooldown, c.next_id, c.stones.next_id]
    h.update(json.dumps(canonical(state), separators=(',', ':')).encode())
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--turns', type=int, default=20)
    p.add_argument('--counts', type=int, nargs='+', default=[100, 500, 1000])
    p.add_argument('--scenarios', nargs='+', choices=['distributed', 'contact'], default=['distributed', 'contact'])
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as out:
        header = dict(platform=platform.platform(), cpu=platform.processor(), python=platform.python_version(),
                      numpy=np.__version__, map_size=512, seed=7, turns_requested=args.turns, profiled=False)
        out.write(json.dumps(header)+'\n')
        print(json.dumps(header), flush=True)
        for scenario in args.scenarios:
            for count in args.counts:
                start = perf_counter()
                e = populated(count, scenario)
                setup = perf_counter()-start
                total = e.construction.soil_total()
                durations, populations, hashes = [], [], [full_fingerprint(e)]
                for _ in range(args.turns):
                    if e.ended: break
                    start = perf_counter()
                    e.advance(1)
                    assert np.all(e.world.terrain.occupancy <= e.world.terrain.capacity)
                    durations.append(perf_counter()-start)
                    assert e.construction.soil_total() == total
                    populations.append(len(e.world.ants))
                    hashes.append(full_fingerprint(e))
                record = dict(scenario=scenario, initial_ants=count, final_ants=len(e.world.ants),
                              population_min=min(populations), population_max=max(populations), populations=populations,
                              turns=e.turn, setup_seconds=round(setup, 4), simulation_seconds=round(sum(durations), 4),
                              mean_ms_per_turn=round(1000*sum(durations)/len(durations), 3),
                              max_ms_per_turn=round(1000*max(durations), 3), turn_ms=[round(t*1000, 6) for t in durations],
                              attacks=e.combat.attacks, ant_deaths=e.lifecycle.ant_deaths,
                              births=sum(c.produced_workers+c.produced_soldiers for c in e.world.colonies),
                              queenless=sum(not c.alive for c in e.world.colonies), ended=e.ended, fingerprints=hashes,
                              soil_total=total, excavations=e.world.terrain.excavated_units,
                              construction_completed=dict(e.construction.completed), active_tasks=len(e.construction.tasks))
                workspace = getattr(e.world.terrain, '_search_workspace', None)
                if workspace:
                    record.update(executed_searches=workspace.searches, expanded_nodes=workspace.expanded)
                out.write(json.dumps(record)+'\n')
                out.flush()
                print(json.dumps({k: v for k, v in record.items() if k not in ('fingerprints', 'turn_ms', 'populations')}), flush=True)

if __name__ == '__main__':
    main()
