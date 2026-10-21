"""Staged UI review scene. All fields displayed are actual simulation data."""
import argparse
import os
from pathlib import Path
from config import Config
from entities.models import Ant, Food
from simulation.engine import Engine
from ai.pheromones import BASE, FOOD, BATTLE


def scene():
    e = Engine(Config(size=64, food_count=0, stone_density=0, large_stone_density=0,
                      reproduction_enabled=False, combat_enabled=False))
    w = e.world
    w.ants.clear()
    w.terrain.occupancy[:] = 0
    for y in range(18, 43):
        if y not in (30, 31):
            e.construction.stones.register(((30, y),), 4)
    w.food = [Food(w.allocate_id(), (26, 26), 'large', 25, 16, age=10),
              Food(w.allocate_id(), (45, 42), 'medium', 10, 8, age=8),
              Food(w.allocate_id(), (12, 12), 'small', 5, 4, age=4)]
    for f, positions in enumerate(([(18, 25), (22, 27), (26, 30), (28, 31)],
                                    [(33, 28), (36, 29), (34, 32), (38, 31)],
                                    [(23, 38), (25, 36), (28, 35), (27, 40)],
                                    [(34, 36), (35, 38), (39, 36), (41, 40)])):
        for i, p in enumerate(positions):
            a = Ant(w.allocate_id(), f, p, kind='soldier' if i % 2 else 'worker')
            a.path = [p]
            w.ants.append(a)
            w.terrain.occupancy[p[1], p[0]] += 1
        c = w.colonies[f]
        c.produced_workers = 12
        c.received_half = 24
    # Deposits use the same real pheromone system as ants. Separate branches show
    # the three channels, overlap, faction colors, and a decayed low-strength tail.
    paths = (
        [(x, 27) for x in range(12, 30)],
        [(x, 31) for x in range(31, 51)],
        [(25, y) for y in range(34, 51)],
        [(x, 38) for x in range(32, 51)])
    for f, path in enumerate(paths):
        for i, p in enumerate(path):
            e.pheromones.reinforce(f, BASE, p, 4+i*.45)
            for c, delta in ((FOOD, (0, 1)), (BATTLE, (0, -1))):
                q = p[0]+delta[0], p[1]+delta[1]
                if w.terrain.capacity[q[1], q[0]]:
                    e.pheromones.reinforce(f, c, q, 5+(i % 5)*2)
    # Queenless red retains only ant and historical-trail influence.
    w.colonies[0].queen.hp = 0
    e.lifecycle.cleanup(0)
    e.food.rebuild_scent()
    e.turn = w.turn = 10
    e.paused = True
    selected = w.ants[2]
    selected.hp = 4
    selected.known_food[w.food[0].id] = w.food[0].position
    e.fsm.prepare(selected)
    return e, selected


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    import pygame
    from ui.renderer import Renderer
    pygame.init()
    try:
        e, selected = scene()
        r = Renderer(pygame.display.set_mode((1200, 800)), e)
        r.selected_id = selected.id
        for name in ('scent', 'pheromones', 'territory', 'all'):
            for key in r.overlays.enabled:
                r.overlays.enabled[key] = name == 'all' or key == name
            r.draw(e)
            caption = f'STAGED ACTUAL FIELDS / {name.upper()} / gray = contested influence / not ownership'
            pygame.draw.rect(r.screen, (20, 23, 28), (0, 770, 860, 30))
            r.screen.blit(r.font.render(caption, True, (255, 255, 255)), (12, 776))
            pygame.image.save(r.screen, str(args.output_dir/f'PHASE4C_{name.upper()}.png'))
        for key in r.overlays.enabled: r.overlays.enabled[key] = key == 'pheromones'
        r.overlays.faction, r.overlays.channel = 0, BATTLE
        r.draw(e)
        pygame.image.save(r.screen, str(args.output_dir/'PHASE4C_TRAIL_FILTER.png'))
        # Additional overview at default map size, with the actual naturally
        # initialized world (not a 64×64 image mislabeled as 512×512).
        e = Engine(Config())
        for _ in range(8): e.advance(1)
        r = Renderer(r.screen, e)
        for key in r.overlays.enabled: r.overlays.enabled[key] = True
        r.draw(e)
        pygame.image.save(r.screen, str(args.output_dir/'PHASE4C_512_OVERVIEW.png'))
        r.focus(e, 0)
        r.draw(e)
        pygame.image.save(r.screen, str(args.output_dir/'PHASE4C_512_FOCUS.png'))
    finally:
        pygame.quit()

if __name__ == '__main__':
    main()
