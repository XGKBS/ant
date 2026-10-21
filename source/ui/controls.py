import pygame
from ui import camera

class Controls:
    def __init__(self):
        self.cap_text = None
        self.was_paused = False
        self.drag_button = None
        self.drag_last = None
        self.request = None
        self.cap_selected = False

    def handle(self, event, engine, renderer):
        self.request = None
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.WINDOWFOCUSLOST:
            self.drag_button = self.drag_last = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (2, 3):
            if renderer.geometry(engine)[0].collidepoint(event.pos):
                self.drag_button, self.drag_last = event.button, event.pos
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == self.drag_button:
            self.drag_button = self.drag_last = None
            return True
        if event.type == pygame.MOUSEMOTION and self.drag_button is not None:
            delta = event.pos[0]-self.drag_last[0], event.pos[1]-self.drag_last[1]
            camera.pan(renderer, engine, delta)
            self.drag_last = event.pos
            return True
        if event.type == pygame.MOUSEWHEEL:
            position = getattr(event, 'pos', pygame.mouse.get_pos())
            if position[0] >= renderer.geometry(engine)[0].w:
                renderer.panel_scroll -= event.y*54
            else:
                camera.zoom_at(renderer, engine, 1.2**event.y, position)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.drag_button is not None:
                return True
            action = next((a for a, rect in renderer.action_rects.items() if rect.collidepoint(event.pos)), None)
            if action is not None:
                self.request = action
                return True
            if not renderer.click_menu(event.pos):
                renderer.inspect(engine, event.pos)
        if event.type != pygame.KEYDOWN:
            return True
        key = event.key
        if key == pygame.K_SPACE:
            if getattr(event, 'repeat', False):
                return True
            if self.cap_text is not None:
                self.cap_text = None
                engine.paused = self.was_paused
            engine.paused = not engine.paused
            self.drag_button = self.drag_last = None
            return True
        if self.cap_text is not None:
            if key in (pygame.K_RETURN, pygame.K_ESCAPE):
                if key == pygame.K_RETURN:
                    if self.cap_text and int(self.cap_text) <= 0:
                        return True
                    engine.max_turns = int(self.cap_text) if self.cap_text else None
                    if engine.max_turns is not None and engine.turn >= engine.max_turns:
                        engine.finish_limit()
                self.cap_text = None
                engine.paused = self.was_paused
            elif key == pygame.K_BACKSPACE:
                self.cap_text = '' if self.cap_selected else self.cap_text[:-1]
                self.cap_selected = False
            elif key == pygame.K_a and getattr(event, 'mod', 0) & pygame.KMOD_CTRL:
                self.cap_selected = True
            elif event.unicode in '0123456789' and event.unicode and len(self.cap_text) < 9:
                self.cap_text = ('' if self.cap_selected else self.cap_text)+event.unicode
                self.cap_selected = False
            return True
        if key == pygame.K_m:
            renderer.overlays.menu_open = not renderer.overlays.menu_open
        elif key in (pygame.K_s, pygame.K_p, pygame.K_c):
            renderer.overlays.toggle({pygame.K_s: 'scent', pygame.K_p: 'pheromones', pygame.K_c: 'territory'}[key])
        elif key == pygame.K_g:
            renderer.overlays.cycle_faction()
        elif key == pygame.K_h:
            renderer.overlays.cycle_channel()
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            engine.speed = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 4, pygame.K_4: 8}[key]
        elif key == pygame.K_e:
            engine.end()
        elif key == pygame.K_r:
            engine.reset()
            renderer.rebuild(engine)
        elif key == pygame.K_t:
            self.was_paused = engine.paused
            engine.paused = True
            self.cap_text = str(engine.max_turns or '')
            self.cap_selected = True
        elif key in (pygame.K_HOME, pygame.K_v):
            renderer.overview()
        elif key == pygame.K_f:
            renderer.focus(engine, (renderer.focus_faction+1) % 4)
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            dx, dy = {pygame.K_LEFT: (60, 0), pygame.K_RIGHT: (-60, 0), pygame.K_UP: (0, 60), pygame.K_DOWN: (0, -60)}[key]
            camera.pan(renderer, engine, (dx, dy))
        return True
