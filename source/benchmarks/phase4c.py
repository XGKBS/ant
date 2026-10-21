"""UI-only render costs, then paired simulation replays with/off overlays.

Cached frames and forced full rebuilds are measured separately. No simulation
frequency, data accuracy, ant count or behavior is changed for rendering speed.
"""
import argparse
import gc
import json
import os
import platform
from pathlib import Path
from time import perf_counter
import tracemalloc
import numpy as np
from benchmarks.phase3 import populated
from benchmarks.phase4b import full_fingerprint

MODES = ('none', 'scent', 'pheromones', 'territory', 'all')

def distribution(samples):
    return dict(mean_ms=round(np.mean(samples)*1000, 3), worst_ms=round(max(samples)*1000, 3),
                p95_ms=round(float(np.percentile(samples, 95))*1000, 3))

def settings(renderer, mode):
    for name in renderer.overlays.enabled:
        renderer.overlays.enabled[name] = mode == 'all' or mode == name

def render_benchmark(args, output, screen):
    import pygame
    from ui.renderer import Renderer
    for count in args.counts:
        e = populated(count, 'distributed', size=args.size)
        for _ in range(5): e.advance(1)
        checkpoint = full_fingerprint(e)
        for view in ('overview', 'focus'):
            for mode in MODES:
                r = Renderer(screen, e)
                if view == 'focus': r.focus(e, 0)
                settings(r, mode)
                r.draw(e)
                builds = dict(r.overlays.builds)
                samples = []
                for _ in range(args.frames):
                    start = perf_counter()
                    r.draw(e)
                    pygame.display.flip()
                    samples.append(perf_counter()-start)
                assert builds == r.overlays.builds
                cold = []
                for _ in range(args.refreshes):
                    start = perf_counter()
                    r.overlays.invalidate()
                    r.draw(e)
                    pygame.display.flip()
                    cold.append(perf_counter()-start)
                assert checkpoint == full_fingerprint(e)
                record = dict(kind='render', size=args.size, start_ants=count, actual_ants=len(e.world.ants),
                              sample_turn=e.turn, ended=e.ended,
                              view=view, zoom=r.zoom, mode=mode, frames=args.frames, rebuilds=args.refreshes,
                              cached=distribution(samples), full_rebuild=distribution(cold),
                              overlay_cache_bytes=r.overlays.cache_bytes())
                output.write(json.dumps(record)+'\n')
                output.flush()
                print(json.dumps(record), flush=True)
        del e, r
        gc.collect()

def simulation_benchmark(args, output, screen):
    import pygame
    from ui.renderer import Renderer
    for count in args.counts:
        engines = [populated(count, 'distributed', size=args.size) for _ in range(2)]
        renderers = [Renderer(screen, e) for e in engines]
        settings(renderers[1], 'all')
        timings, draws, populations, hashes = [[], []], [[], []], [], []
        for turn in range(args.turns):
            if engines[0].ended:
                break
            # Alternate order to avoid always warming the same mode first.
            for i in (range(2) if turn % 2 == 0 else range(1, -1, -1)):
                e, r = engines[i], renderers[i]
                start = perf_counter()
                e.advance(1)
                assert np.all(e.world.terrain.occupancy <= e.world.terrain.capacity)
                timings[i].append(perf_counter()-start)
                start = perf_counter()
                r.draw(e)
                pygame.display.flip()
                draws[i].append(perf_counter()-start)
            a, b = (full_fingerprint(e) for e in engines)
            assert a == b, (count, turn)
            hashes.append(a)
            populations.append(len(engines[0].world.ants))
        e = engines[0]
        record = dict(kind='simulation', size=args.size, start_ants=count, final_ants=len(e.world.ants),
                      turns=e.turn, populations=populations, identical_every_turn=True, fingerprints=hashes,
                      simulation_off=distribution(timings[0]), simulation_all=distribution(timings[1]),
                      rendering_off=distribution(draws[0]), rendering_all=distribution(draws[1]),
                      births=sum(c.produced_workers+c.produced_soldiers for c in e.world.colonies),
                      deaths=e.lifecycle.ant_deaths, attacks=e.combat.attacks,
                      soil_total=e.construction.soil_total())
        output.write(json.dumps(record)+'\n')
        output.flush()
        print(json.dumps({k: v for k, v in record.items() if k not in ('fingerprints', 'populations')}), flush=True)

def memory_benchmark(args, output, screen):
    from ui.renderer import Renderer
    e = populated(100, 'distributed', size=args.size)
    r = Renderer(screen, e)
    r.focus(e, 0)
    settings(r, 'all')
    gc.collect()
    tracemalloc.start()
    r.draw(e)
    live, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    record = dict(kind='memory', size=args.size, mode='all', view='focus',
                  overlay_cache_bytes=r.overlays.cache_bytes(), python_numpy_live_bytes=live,
                  python_numpy_peak_bytes=peak,
                  note='Explicit cache includes SDL surfaces; tracemalloc excludes SDL allocations. Values overlap; do not add them.')
    output.write(json.dumps(record)+'\n')
    print(json.dumps(record), flush=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--size', type=int, default=512)
    p.add_argument('--counts', type=int, nargs='+', default=[100, 500, 1000])
    p.add_argument('--frames', type=int, default=120)
    p.add_argument('--refreshes', type=int, default=8)
    p.add_argument('--turns', type=int, default=20)
    p.add_argument('--part', choices=['all', 'render', 'simulation'], default='all')
    args = p.parse_args()
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    import pygame
    pygame.init()
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        screen = pygame.display.set_mode((1200, 800))
        with args.output.open('w', encoding='utf-8') as output:
            header = dict(kind='environment', platform=platform.platform(), cpu=platform.processor(),
                          python=platform.python_version(), numpy=np.__version__, pygame=pygame.version.ver,
                          driver=pygame.display.get_driver(), display=[1200, 800], seed=7)
            output.write(json.dumps(header)+'\n')
            print(json.dumps(header), flush=True)
            if args.part in ('all', 'render'):
                render_benchmark(args, output, screen)
                memory_benchmark(args, output, screen)
            if args.part in ('all', 'simulation'):
                simulation_benchmark(args, output, screen)
    finally:
        pygame.quit()

if __name__ == '__main__':
    main()
