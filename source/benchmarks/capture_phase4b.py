"""Deterministic staged scenes, completed through the ordinary autonomous FSM."""
import argparse
import os
from pathlib import Path
from config import Config
from entities.models import Ant, Food
from simulation.engine import Engine

def scene(kind):
    e = Engine(Config(size=32, food_count=0, stone_density=0, large_stone_density=0,
                      reproduction_enabled=False, combat_enabled=False, perks=('production',)*4))
    w, c = e.world, e.construction
    w.ants.clear()
    w.terrain.occupancy[:] = 0
    def put(p, kind='soldier'):
        a = Ant(w.allocate_id(), 0, p, kind=kind)
        w.ants.append(a)
        w.terrain.occupancy[p[1], p[0]] += 1
        return a
    if kind in ('stone', 'large_stone'):
        large = kind == 'large_stone'
        for y in range(32):
            if not large or y not in (10, 11): c.stones.register([(10, y)], 4)
        if large:
            c.stones.register([(10, 10), (11, 10), (10, 11), (11, 11)], 16, 3)
            w.terrain.dig(9, 10)
            w.terrain.dig(9, 11)
        selected = put((9, 10), 'worker')
        food_pos = (13, 10) if large else (12, 10)
        selected.known_food[999] = food_pos
        w.food = [Food(999, food_pos, 'small', 5, 4, age=4)]
        positions = ([(x, y) for y in range(8, 14) for x in (7, 8, 9) if (x, y) != (9, 10)][:16]
                     if large else [(8, 9), (8, 10), (8, 11), (9, 8), (9, 12), (7, 10), (7, 11)])
        for p in positions: put(p)
        finish = lambda: c.completed['stone'] > 0
    elif kind == 'composition':
        c.stones.register([(7, 6)], 4)
        c.stones.register([(8, 6)], 4)
        ants = [put(p) for p in [(7, 5), (8, 5), (6, 5), (9, 5), (6, 6), (9, 6), (7, 4), (8, 4)]]
        selected = ants[0]
        for x in range(15, 20):
            w.terrain.dig(x, 15)
            w.terrain.withdraw((x, 15))
            w.terrain.deposit((7, 5), 1)
        w.terrain.withdraw((7, 5))
        selected.soil_cargo = 1
        finish = lambda: c.completed['compose'] > 0
    else:
        selected = put((6, 5))
        c.dig(selected, (7, 5), 0)
        finish = lambda: c.completed['fill'] > 0
    e.food.rebuild_scent()
    e._plan()
    return e, selected, finish

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
        screen = pygame.display.set_mode((1200, 800))
        for kind in ('soil', 'stone', 'large_stone', 'composition'):
            e, selected, complete = scene(kind)
            renderer = Renderer(screen, e)
            renderer.selected_id = selected.id
            total = e.construction.soil_total()
            for label in ('BEFORE', 'DURING', 'AFTER'):
                if label == 'DURING':
                    e.advance(1)
                    helper = next((a for a in e.world.ants if a.construction_task is not None), selected)
                    renderer.selected_id = helper.id
                if label == 'AFTER':
                    for _ in range(30):
                        if complete(): break
                        e.advance(1)
                        if complete(): break
                    assert complete(), kind
                    assert e.construction.soil_total() == total
                    helper = next((a for a in e.world.ants if a.last_action in ('fill', 'move-stone', 'compose-stone')), selected)
                    renderer.selected_id = helper.id
                renderer.draw(e)
                caption = f'STAGED AUTONOMOUS {kind.upper()} / {label} / turn {e.turn} / conserved soil {total}'
                pygame.draw.rect(screen, (20, 23, 28), (0, 770, 860, 30))
                screen.blit(renderer.font.render(caption, True, (255, 255, 255)), (12, 776))
                pygame.image.save(screen, str(args.output_dir/f'PHASE4B_{kind.upper()}_{label}.png'))
                print(caption)
    finally:
        pygame.quit()

if __name__ == '__main__':
    main()
