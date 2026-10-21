import math
import pygame
import numpy as np
from config import COLORS
from systems.perks import load, movement
from ui.overlays import Overlays, CHANNELS
from ui import camera
from ui.widgets import button, PANEL, ACCENT, text_lines
from ui.food_economy import economy_lines

NAMES = ('Red', 'Yellow', 'Blue', 'Green')

class Renderer:
    """Camera, hit testing and inspection are observational UI state only."""
    def __init__(self, screen, engine, startup_focus=None):
        self.screen = screen
        self.font = pygame.font.Font(None, 20)
        self.startup_focus = startup_focus
        self.focus_faction = -1
        self.selected_id = None
        self.selected_station = None
        self.selected_depot = self.selected_site = None
        self.economy_open = False
        self.economy_rect = None
        self.overlays = Overlays()
        self.menu_rects = {}
        self.action_rects = {}
        self.panel_scroll = 0
        self.pending_turns = 0
        self.rebuild(engine)

    def rebuild(self, engine, reset_camera=True):
        palette = np.array([(94, 72, 49), (155, 123, 81), (110, 115, 122), (65, 72, 83), (45, 37, 29), (178, 145, 105)], dtype=np.uint8)
        self.terrain = pygame.surfarray.make_surface(palette[engine.world.terrain.cells].transpose(1, 0, 2))
        self.terrain_revision = engine.world.terrain.revision
        if reset_camera:
            self.overlays.invalidate()
            self.overview()
            self.selected_id = None
            self.selected_station = None
            self.selected_depot = self.selected_site = None
            if self.startup_focus is not None:
                self.focus(engine, self.startup_focus)

    def overview(self):
        self.zoom, self.offset = 1.0, [0.0, 0.0]

    def geometry(self, engine):
        viewport = pygame.Rect(0, 0, max(200, self.screen.get_width()-340), self.screen.get_height())
        size = engine.config.size
        scale = min(viewport.w, viewport.h)/size*self.zoom
        origin = ((viewport.w-size*scale)/2+self.offset[0], (viewport.h-size*scale)/2+self.offset[1])
        return viewport, scale, origin

    def point(self, engine, pos):
        _, scale, origin = self.geometry(engine)
        return round(origin[0]+(pos[0]+0.5)*scale), round(origin[1]+(pos[1]+0.5)*scale)

    def focus(self, engine, faction):
        self.focus_faction = faction
        self.zoom = min(16.0, max(1.0, engine.config.size/64))
        self.offset = [0.0, 0.0]
        viewport, scale, origin = self.geometry(engine)
        x, y = engine.world.colonies[faction].queen.position
        x += 12 if x < engine.config.size/2 else -10
        y += 12 if y < engine.config.size/2 else -10
        self.offset = [viewport.w/2-(origin[0]+x*scale), viewport.h/2-(origin[1]+y*scale)]
        for axis, extent in enumerate((viewport.w, viewport.h)):
            new_origin = min(0, max(extent-engine.config.size*scale, origin[axis]+self.offset[axis]))
            self.offset[axis] = new_origin-origin[axis]

    def inspect(self, engine, mouse):
        viewport, _, _ = self.geometry(engine)
        if not viewport.collidepoint(mouse):
            return
        self.selected_depot = self.selected_site = None
        hits = []
        for ant in engine.world.ants:
            p = self.point(engine, engine.display_position(ant))
            d = (p[0]-mouse[0])**2+(p[1]-mouse[1])**2
            if d <= 100:
                hits.append((d, ant.id))
        hits.sort()
        ids = [ant_id for _, ant_id in hits]
        if ids:
            self.selected_station = None
            self.selected_id = ids[(ids.index(self.selected_id)+1) % len(ids)] if self.selected_id in ids else ids[0]
            self.panel_scroll = 100000
        else:
            self.selected_id = None
            stations = [s for s in engine.world.stations if sum((a-b)**2 for a,b in zip(self.point(engine,s.position),mouse)) <= 100]
            self.selected_station = min(stations,key=lambda s:s.id).id if stations else None
            if stations:
                self.panel_scroll = 100000

        if not ids and self.selected_station is None:
            _, scale, origin = self.geometry(engine)
            cell = (int((mouse[0]-origin[0])/scale), int((mouse[1]-origin[1])/scale))
            self.selected_depot = next((d.id for d in engine.world.depots if cell in d.footprint), None)
            self.selected_site = next((j.id for j in engine.construction.tasks.values()
                                       if j.kind == 'depot' and cell in engine.depots.cells(j.target)), None)
            if self.selected_depot is not None or self.selected_site is not None:
                self.panel_scroll = 100000

    def click_menu(self, mouse):
        if self.economy_rect is not None and self.economy_rect.collidepoint(mouse):
            self.economy_open = not self.economy_open
            return True
        for action, rect in self.menu_rects.items():
            if action not in ('menu','economy') and not self.overlays.menu_open:
                continue
            if rect.collidepoint(mouse):
                if action == 'economy':
                    self.economy_open = not self.economy_open
                elif action == 'menu':
                    self.overlays.menu_open = not self.overlays.menu_open
                elif action == 'faction':
                    self.overlays.cycle_faction()
                elif action == 'channel':
                    self.overlays.cycle_channel()
                else:
                    self.overlays.toggle(action)
                return True
        return False

    def draw(self, engine, cap_text=None):
        camera.clamp(self, engine)
        if self.terrain_revision != engine.world.terrain.revision:
            self.rebuild(engine, reset_camera=False)
        screen = self.screen
        screen.fill((20, 23, 28))
        viewport, scale, origin = self.geometry(engine)
        size = engine.config.size
        screen.set_clip(viewport)
        # Crop before scaling so high zoom cannot allocate a huge world surface.
        left, top = max(0, math.floor(-origin[0]/scale)), max(0, math.floor(-origin[1]/scale))
        right = min(size, math.ceil((viewport.w-origin[0])/scale))
        bottom = min(size, math.ceil((viewport.h-origin[1])/scale))
        if right > left and bottom > top:
            crop = self.terrain.subsurface((left, top, right-left, bottom-top))
            scaled = pygame.transform.scale(crop, (max(1, round(crop.get_width()*scale)), max(1, round(crop.get_height()*scale))))
            screen.blit(scaled, (round(origin[0]+left*scale), round(origin[1]+top*scale)))
        self.overlays.draw(screen, engine, scale, origin, (left, top, right, bottom))
        for pos, units in engine.world.terrain.loose_soil.items():
            p = self.point(engine, pos)
            pygame.draw.rect(screen, (225, 190, 135), (p[0]-2, p[1]-2, 4, 4))
        for food in engine.world.food:
            if food.units > 0:
                pygame.draw.circle(screen, (240, 170, 85), self.point(engine, food.position), max(3, round(scale*0.35)))
        for station in engine.world.stations:
            p = self.point(engine,station.position)
            radius = max(5,min(10,round(scale*.4)))
            rect = pygame.Rect(p[0]-radius,p[1]-radius,2*radius,2*radius)
            pygame.draw.rect(screen,(16,30,36),rect)
            pygame.draw.rect(screen,(230,245,245),rect,2)
            color = (100,235,220) if station.units > 0 else (135,150,155)
            pygame.draw.line(screen,color,(p[0]-radius+2,p[1]),(p[0]+radius-2,p[1]),2)
            pygame.draw.line(screen,color,(p[0],p[1]-radius+2),(p[0],p[1]+radius-2),2)
            if station.id == self.selected_station:
                pygame.draw.rect(screen,(255,225,120),rect.inflate(6,6),1)
        for job in engine.construction.tasks.values():
            if job.kind != 'depot':
                continue
            x, y = job.target
            width, height = engine.config.depot_footprint
            rect = pygame.Rect(origin[0]+x*scale, origin[1]+y*scale, max(6,width*scale), max(6,height*scale))
            pygame.draw.rect(screen, (35,30,25), rect)
            pygame.draw.rect(screen, COLORS[job.faction], rect, 1)
            pygame.draw.line(screen, (245,180,70), rect.topleft, rect.bottomright, 1)
            bar = pygame.Rect(rect.left,rect.bottom+2, max(1,int(rect.w*min(20,job.progress)/20)),3)
            pygame.draw.rect(screen,(255,210,95),bar)
            if scale >= 8 and rect.colliderect(viewport):
                label=self.font.render(f'Site #{job.id}: {min(20,int(job.progress))}/20 | {job.active_builders} builders',True,(255,225,130))
                screen.blit(label,(min(max(2,rect.x),viewport.w-label.get_width()),max(2,rect.y-18)))
        for depot in engine.world.depots:
            x, y = depot.position
            rect = pygame.Rect(origin[0]+x*scale, origin[1]+y*scale,
                               max(5, depot.dimensions[0]*scale), max(5, depot.dimensions[1]*scale))
            pygame.draw.rect(screen, COLORS[depot.faction], rect, 2)
            pygame.draw.line(screen, (245, 230, 175), rect.midleft, rect.midright, 2)
            if scale >= 8 and rect.colliderect(viewport):
                label=self.font.render(f'Depot #{depot.id} | {"linked" if engine.depots.connected(depot) else "disconnected"}',True,(245,230,175))
                screen.blit(label,(min(max(2,rect.x),viewport.w-label.get_width()),max(2,rect.y-18)))
        for colony in engine.world.colonies:
            x, y = colony.queen.position
            rect = pygame.Rect(origin[0]+x*scale, origin[1]+y*scale, max(5, 2*scale), max(5, 2*scale))
            if colony.alive:
                pygame.draw.rect(screen, COLORS[colony.faction], rect)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1)
            if not colony.alive:
                pygame.draw.line(screen, (240, 240, 240), rect.topleft, rect.bottomright)
        for ant in engine.world.ants:
            p = self.point(engine, engine.display_position(ant))
            radius = max(6 if ant.kind == 'soldier' else 4, min(9, round(scale*0.3)))
            pygame.draw.circle(screen, (15, 15, 18), p, radius+2)
            if ant.kind == 'honeypot':
                body = pygame.Rect(p[0]-radius, p[1]-radius, 2*radius, 2*radius+2)
                pygame.draw.ellipse(screen, COLORS[ant.faction], body)
                fill = round((2*radius-2)*ant.stored_food/10)
                pygame.draw.rect(screen, (255,220,115), (p[0]-radius+1, p[1]+radius-fill, 2*radius-2, fill))
                pygame.draw.ellipse(screen, (255,240,185), body, 1)
            elif ant.kind == 'soldier':
                pygame.draw.polygon(screen, COLORS[ant.faction], [(p[0], p[1]-radius), (p[0]+radius, p[1]), (p[0], p[1]+radius), (p[0]-radius, p[1])])
            else:
                pygame.draw.circle(screen, COLORS[ant.faction], p, radius)
            pygame.draw.line(screen, (255, 255, 255), p, (p[0]+ant.heading[0]*(radius+2), p[1]+ant.heading[1]*(radius+2)), 1)
            if ant.cargo:
                pygame.draw.circle(screen, (255, 235, 150), (p[0], p[1]-radius-2), 2)
            if ant.soil_cargo:
                pygame.draw.rect(screen, (225, 190, 135), (p[0]-2, p[1]-radius-4, 4, 4))
            if ant.id == self.selected_id:
                pygame.draw.circle(screen, (255, 255, 255), p, radius+5, 1)
                if ant.target is not None:
                    pygame.draw.circle(screen, (245, 245, 245), self.point(engine, ant.target), 5, 1)
        screen.set_clip(None)
        pygame.draw.rect(screen, PANEL, (viewport.w, 0, 340, screen.get_height()))
        pygame.draw.line(screen, ACCENT, (viewport.w, 0), (viewport.w, screen.get_height()), 2)
        self.action_rects = {}
        actions = [('pause', 'Resume' if engine.paused else 'Pause'), ('menu_game', 'Menu'), ('end', 'End'),
                   ('restart', 'Restart'), ('new_game', 'New game'), ('settings', 'Settings'),
                   ('overview', 'Overview'), ('colony', 'Colony'), ('cap', 'Turn cap')]
        for index, (action, label) in enumerate(actions):
            rect = pygame.Rect(viewport.w+10+(index%3)*108, 10+(index//3)*31, 102, 27)
            self.action_rects[action] = rect
            button(screen, self.font, rect, label, selected=action == 'pause' and engine.paused,
                   enabled=not engine.ended or action not in ('pause','end'))
        for index, speed in enumerate((1, 2, 4, 8)):
            rect = pygame.Rect(viewport.w+10+index*81, 104, 75, 27)
            self.action_rects['speed_'+str(speed)] = rect
            button(screen, self.font, rect, str(speed)+'x', selected=engine.speed == speed)
        backlog = int(engine.progress+self.pending_turns) if not engine.ended else 0
        status = ['ANT COLONIES', f'Turn {engine.turn} | {engine.speed}x | queued {backlog}',
                 ('ENDED' if engine.ended else ('PAUSED' if engine.paused else 'RUNNING')) + f' | cap: {engine.max_turns or "unlimited"}',
                 ]
        line_height = self.font.get_linesize()+3
        if engine.outcome:
            status += text_lines(self.font, engine.outcome, 312)
        for i, line in enumerate(status):
            screen.blit(self.font.render(line, True, (230, 233, 238)), (viewport.w+12, 144+i*line_height))
        content_top = 144+len(status)*line_height+8
        content_bottom = screen.get_height()-22
        lines = []
        self.menu_rects = {}
        self.economy_rect = None
        menu_rows = {}
        def menu_line(action, label):
            menu_rows[action] = len(lines)
            lines.append(label)
        menu_line('menu', f'MORE INFORMATION [M] {"-" if self.overlays.menu_open else "+"}')
        menu_line('economy', f'FOOD ECONOMY {"-" if self.economy_open else "+"} [click]')
        if self.economy_open:
            lines += economy_lines(engine)
        else:
            lines += ['White + square: public supplies']
        if self.overlays.menu_open:
            for name, label, key in (('scent', 'Food Scent Range', 'S'), ('pheromones', 'Pheromone Trails', 'P'), ('territory', 'Territory Coverage', 'C')):
                menu_line(name, f'[{"x" if self.overlays.enabled[name] else " "}] {label} [{key}]')
            faction = 'All' if self.overlays.faction is None else NAMES[self.overlays.faction]
            channel = 'All' if self.overlays.channel is None else CHANNELS[self.overlays.channel]
            menu_line('faction', f'Trails faction: {faction} [G]')
            menu_line('channel', f'Trails type: {channel} [H]')
            lines += ['Cyan scent | brighter = stronger', 'Trails at zoom: rows B/F/!; cols R/Y/B/G',
                      'Gray contested | blank neutral', 'Influence only, never ownership']
        for colony in engine.world.colonies:
            workers = sum(a.faction == colony.faction and a.kind == 'worker' for a in engine.world.ants)
            soldiers = sum(a.faction == colony.faction and a.kind == 'soldier' for a in engine.world.ants)
            honey = [a for a in engine.world.ants if a.faction == colony.faction and a.kind == 'honeypot']
            lines += [f'{NAMES[colony.faction]}: W {workers} / S {soldiers} / H {len(honey)}',
                      f'Shared food {colony.reserves:g} | H stored {sum(a.stored_food for a in honey):g}',
                      f'Queen {colony.queen.hp:g}/{colony.queen.max_hp:g} | L{int(colony.upgraded)}{" save" if colony.saving_upgrade else ""} | {"alive" if colony.alive else "queenless"}',
                      f'{colony.perk}{" (off)" if not colony.alive else ""} | {colony.threat}',
                      f'{colony.strategic_state} | target reserve {colony.reserve_target}',
                      f'Depots {sum(d.faction == colony.faction for d in engine.world.depots)} | received {sum(d.deposited for d in engine.world.depots if d.faction == colony.faction):g}']
        lines += [f'Delivered {engine.food.delivered:g} | eaten {engine.food.eaten:g}',
                  f'Dug {engine.world.terrain.excavated_units} | attacks {engine.combat.attacks} | queued {len(engine.food.pending)}']
        ant = next((a for a in engine.world.ants if a.id == self.selected_id), None)
        station = next((s for s in engine.world.stations if s.id == self.selected_station),None)
        depot = next((d for d in engine.world.depots if d.id == self.selected_depot), None)
        site = engine.construction.tasks.get(self.selected_site)
        if depot is not None:
            lines += [f'DEPOT #{depot.id} | {NAMES[depot.faction]}',
                      'Connected' if engine.depots.connected(depot) else 'Disconnected: queenless',
                      f'Cumulative received {depot.deposited:g} (not stock)',
                      f'Shared balance {engine.world.colonies[depot.faction].reserves:g}']
        if site is not None and site.kind == 'depot':
            lines += [f'DEPOT SITE #{site.id} | {NAMES[site.faction]}',
                      f'Progress {min(20,int(site.progress))}/20 | active {site.active_builders}',
                      f'Paid {site.paid_half/2:g} | assigned {len(site.crew)}',
                      f'Status: {site.blocked_reason}']
        if station:
            lines += [f'PUBLIC STATION #{station.id} at {station.position}',
                      f'Stored {station.units:g} | next refill {station.next_refill-engine.turn} turns',
                      f'Generated {station.generated_units:g} | collected {station.collected_units:g}',
                      f'Context: {NAMES[station.origin_faction]} (public)', station.placement_reason]
        if ant:
            colony = engine.world.colonies[ant.faction]
            combat = f'{ant.combat_target[0]} #{ant.combat_target[1]}' if ant.combat_target else 'none'
            lines += [f'ANT #{ant.id} | {NAMES[ant.faction]} | {ant.kind}', f'HP {ant.hp:g}/{ant.max_hp} | food {ant.cargo:g}/{load(ant, colony):g}',
                      f'FSM: {ant.state}', f'Activity: {ant.activity}', f'Cached facts: {len(ant.information)}/{engine.config.information_capacity}', f'Last relay/contact: {ant.last_information_turn if ant.last_information_turn>=0 else "none"}', f'Stationary {ant.stationary_turns} | idle {ant.unproductive_idle_turns}', f'Orders: {ant.order_state} #{ant.order_epoch}', f'Cargo source: {ant.cargo_origin}', f'Honeypot stored {ant.stored_food:g}/10' if ant.kind == 'honeypot' else f'Supplier target: {ant.honeypot_id}', f'Position: {ant.position}', f'Target: {ant.target}',
                      f'Combat: {combat}', f'Action: {ant.last_action or "none"} | move {movement(ant, colony)}',
                      f'Soil {ant.soil_cargo} | job {ant.construction_task} | food {ant.food_id}']
        else:
            lines += [f'Ant #{self.selected_id} is no longer alive.' if self.selected_id is not None else 'Click an ant to inspect its live FSM.']
        if cap_text is not None:
            lines += ['Turn cap: ' + cap_text + '_', 'Enter apply | Esc cancel | blank unlimited']
        # Pixel-based wrapping keeps all diagnostics readable at every text size.
        wrapped_lines, remap = [], {}
        for index, line in enumerate(lines):
            remap[index] = len(wrapped_lines)
            wrapped_lines += text_lines(self.font, line, 312)
        lines = wrapped_lines
        menu_rows = {action: remap[index] for action, index in menu_rows.items()}
        self.panel_max_scroll = max(0, len(lines)*line_height-(content_bottom-content_top))
        self.panel_scroll = max(0, min(self.panel_scroll, self.panel_max_scroll))
        screen.set_clip(pygame.Rect(viewport.w+6, content_top, 330, content_bottom-content_top))
        for i, line in enumerate(lines):
            y = content_top+i*line_height-self.panel_scroll
            if y >= content_top and y+line_height <= content_bottom:
                screen.blit(self.font.render(line, True, (230, 233, 238)), (viewport.w+12, y))
        for action, index in menu_rows.items():
            rect = pygame.Rect(viewport.w+8, content_top+index*line_height-self.panel_scroll, 320, line_height)
            visible = rect.clip(pygame.Rect(viewport.w, content_top, 334, content_bottom-content_top))
            if visible.height == rect.height:
                if action == 'economy':
                    self.economy_rect = rect
                else:
                    self.menu_rects[action] = rect
                if rect.collidepoint(pygame.mouse.get_pos()):
                    pygame.draw.rect(screen, ACCENT, rect, 1)
        screen.set_clip(None)
        if self.panel_max_scroll:
            text = self.font.render('Scroll panel for stats / inspection', True, (175, 198, 215))
            screen.blit(text, (viewport.w+10, screen.get_height()-20))
            track = pygame.Rect(screen.get_width()-6, content_top, 4, content_bottom-content_top)
            pygame.draw.rect(screen, (62, 80, 99), track)
            thumb = pygame.Rect(track.x, track.y+int((track.h-24)*self.panel_scroll/self.panel_max_scroll), 4, 24)
            pygame.draw.rect(screen, ACCENT, thumb)
        if engine.paused:
            badge = self.font.render('PAUSED  |  Space or Resume', True, (255, 235, 165))
            pygame.draw.rect(screen, (25, 34, 45), (8, 8, badge.get_width()+16, 28), border_radius=4)
            screen.blit(badge, (16, 14))
