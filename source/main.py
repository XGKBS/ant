import argparse
import os
import sys
from config import Config, PERKS

def run(config, focus=None, auto_start=False, smoke_frames=0, event_hook=None):
    import pygame
    from ui.application import Application
    pygame.init()
    screen = pygame.display.set_mode((1200, 800), pygame.RESIZABLE)
    pygame.display.set_caption('Ant Colonies')
    app = Application(screen, config, startup_focus=focus, auto_start=auto_start)
    clock = pygame.time.Clock()
    app.draw()
    pygame.display.flip()
    frames = 0
    try:
        while app.running:
            elapsed = clock.tick(app.fps)/1000
            if event_hook is not None:
                event_hook(app, frames)
            app.frame(elapsed, pygame.event.get())
            app.draw()
            pygame.display.flip()
            if app.reset_clock:
                # Do not count loading a new world as already-running time.
                clock.tick()
                app.reset_clock = False
            frames += 1
            if smoke_frames and frames >= smoke_frames:
                break
    finally:
        pygame.quit()
    return app

def main(argv=None):
    parser = argparse.ArgumentParser(description='Ant Colonies: graphical setup, simulation and information overlays')
    parser.add_argument('--size', type=int, default=512)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--max-turns', type=int)
    parser.add_argument('--perks', default='production,exploration,warfare,speed', help='Four comma-separated abilities, red/yellow/blue/green. Choices: ' + ', '.join(PERKS))
    parser.add_argument('--focus-colony', choices=('red', 'yellow', 'blue', 'green'), help='Start focused on a colony; Home restores overview')
    parser.add_argument('--smoke-frames', type=int, default=0, help='Render N frames using SDL dummy drivers and exit')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--setup', action='store_true', help='Show the GUI, prefilled with CLI options')
    group.add_argument('--play', action='store_true', help='Start immediately without the main menu')
    argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(argv)
    if args.smoke_frames:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
    perks = tuple(p.strip().lower() for p in args.perks.split(','))
    if len(perks) != 4 or any(p not in PERKS for p in perks):
        parser.error('--perks requires four valid comma-separated abilities')
    try:
        config = Config(size=args.size, seed=args.seed, max_turns=args.max_turns, perks=perks)
    except ValueError as error:
        parser.error(str(error))
    focus = ('red', 'yellow', 'blue', 'green').index(args.focus_colony) if args.focus_colony else None
    explicit = any(option.split('=')[0] in ('--size','--seed','--max-turns','--perks','--focus-colony') for option in argv)
    auto_start = not args.setup and (args.play or explicit or bool(args.smoke_frames))
    return run(config, focus, auto_start, args.smoke_frames)

if __name__ == '__main__':
    main()
