"""Reproducible, explicitly staged regression scene for UI review, not a natural run."""
import argparse
import os
from pathlib import Path
from config import Config
from entities.models import Ant, Food
from simulation.engine import Engine

def scene():
    engine = Engine(Config(size=64, food_count=0, stone_density=0.025, large_stone_density=0.002,
                           perks=('heavy-lifting', 'warfare', 'production', 'sensitivity')))
    world = engine.world
    world.ants.clear()
    world.terrain.occupancy[:] = 0
    def put(faction, position, kind='worker', hp=None):
        world.terrain.set(*position, 0)
        ant = Ant(world.allocate_id(), faction, position, kind=kind, hp=hp)
        ant.path = [position]*(3 if kind == 'worker' else 4)
        world.ants.append(ant)
        world.terrain.occupancy[position[1], position[0]] += 1
        return ant
    attacker = put(1, (1, 2), 'soldier')
    worker = put(0, (5, 2), hp=3)
    worker.cargo = 1.5
    survivor = put(0, (7, 2), 'soldier', hp=10)
    put(0, (59, 2), 'soldier')
    for faction, positions in ((1, [(58, 5), (60, 5)]), (2, [(5, 58), (5, 60)]), (3, [(58, 58), (60, 58)])):
        for position in positions:
            put(faction, position)
    world.colonies[0].queen.hp = 3
    world.colonies[1].upgraded = True
    world.colonies[1].reserves = 8
    world.colonies[2].produced_workers = 9
    world.colonies[2].reserves = 8
    world.colonies[3].reserves = 12
    world.food = [Food(world.allocate_id(), (7, 2), 'small', 5, 4, age=4),
                  Food(world.allocate_id(), (55, 55), 'large', 25, 16, age=16)]
    engine.food.rebuild_scent()
    engine.combat.refresh()
    engine.strategy.assess(0)
    for ant in world.ants:
        engine.fsm.prepare(ant)
    return engine, attacker, survivor

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    import pygame
    from ui.renderer import Renderer
    pygame.init()
    try:
        engine, attacker, survivor = scene()
        renderer = Renderer(pygame.display.set_mode((1200, 800)), engine)
        renderer.selected_id = attacker.id
        renderer.draw(engine)
        pygame.image.save(renderer.screen, str(args.output_dir/'PHASE3_COMBAT.png'))
        engine.advance(1)
        assert engine.world.colonies[0].death_turn == 1
        renderer.selected_id = survivor.id
        renderer.draw(engine)
        pygame.image.save(renderer.screen, str(args.output_dir/'PHASE3_QUEENLESS.png'))
    finally:
        pygame.quit()

if __name__ == '__main__':
    main()
