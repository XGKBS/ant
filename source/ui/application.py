"""Graphical session flow and active-time accounting around the unchanged engine."""
from dataclasses import replace
import pygame
from config import Config, PERKS, COLORS
from simulation.engine import Engine
from ui.renderer import Renderer, NAMES
from ui.controls import Controls
from ui.widgets import button, wrapped, BG, TEXT, MUTED, ACCENT

ABILITIES = {
    'production': 'Ten produced workers upgrade the queen free. After upgrade, ten births of one type queue a free ant. One birth per turn still applies.',
    'exploration': 'Workers cost 1.5 food instead of 2.',
    'warfare': 'Soldiers cost 1.5 food instead of 2. The queen must first upgrade.',
    'speed': 'Workers move 3 cells per turn instead of 2.',
    'blitz': 'Soldiers move 4 cells per turn instead of 3.',
    'greed': 'Collection from five distinct sources of one tier earns a token preventing the next downgrade of that tier.',
    'heavy-lifting': 'Each ant carries 1.5 units instead of 1, including cooperative stone capacity.',
    'sensitivity': 'Worker sensing increases to 3 cells; queen alarm radius increases to 15.'}

class Application:
    def __init__(self, screen, config=Config(), startup_focus=None, auto_start=False):
        self.screen = screen
        self.config = config
        self.startup_focus = startup_focus
        self.engine = self.renderer = None
        self.controls = Controls()
        self.mode = 'main'
        self.running = True
        self.fps = 60
        self.text_size = 20
        self.buttons = {}
        self.modal_rect = None
        self.fields = {}
        self.focused_field = None
        self.selected_text = False
        self.draft_size = config.size
        self.draft_perks = list(config.perks)
        self.draft_seed = str(config.seed)
        self.draft_cap = str(config.max_turns or '')
        self.selected_faction = 0
        self.message = ''
        self.settings_return = 'main'
        self.pending_turns = 0.0
        self.previous_active = False
        self.previous_speed = 1
        self.reset_clock = False
        self.last_tick_seconds = 0
        self.text_echo = None
        self.menu_canvas = pygame.Surface((1000, 760))
        if auto_start:
            self.start(config)

    @property
    def active(self):
        return self.mode == 'game' and self.engine is not None and not self.engine.paused and not self.engine.ended

    def start(self, config):
        # Construction/init time is not gameplay time. Old jobs and caches belong
        # only to the old engine, which is released after these replacements.
        old_overlays = None if self.renderer is None else self.renderer.overlays
        self.engine = Engine(config)
        self.config = config
        self.renderer = Renderer(self.screen, self.engine, startup_focus=self.startup_focus)
        if old_overlays is not None:
            self.renderer.overlays.enabled = dict(old_overlays.enabled)
            self.renderer.overlays.faction, self.renderer.overlays.channel = old_overlays.faction, old_overlays.channel
        self.renderer.font = pygame.font.Font(None, self.text_size)
        self.controls = Controls()
        self.mode = 'game'
        self.pending_turns = 0
        self.previous_active = False
        self.reset_clock = True
        self.focused_field = None
        self.message = ''

    def setup(self):
        if self.engine is not None:
            self.engine.paused = True
        self.draft_size = self.config.size
        self.draft_perks = list(self.config.perks)
        cap = self.engine.max_turns if self.engine is not None else self.config.max_turns
        self.draft_seed, self.draft_cap = str(self.config.seed), str(cap or '')
        self.mode, self.message, self.focused_field = 'setup', '', None
        self.controls.drag_button = self.controls.drag_last = None

    def pause(self):
        if self.engine is None:
            return
        self.controls.drag_button = self.controls.drag_last = None
        if self.controls.cap_text is not None:
            self.controls.cap_text = None
            self.engine.paused = self.controls.was_paused
        if self.engine.ended:
            self.mode = 'game' if self.mode == 'pause' else 'pause'
        else:
            self.engine.paused = not self.engine.paused
            self.mode = 'pause' if self.engine.paused else 'game'

    def action(self, action):
        e, r = self.engine, self.renderer
        if action == 'quit':
            self.running = False
        elif action in ('new_game', 'new'):
            self.setup()
        elif action == 'back_setup':
            self.mode = 'main' if e is None else 'pause'
        elif action == 'start':
            try:
                config = replace(self.config, size=self.draft_size, perks=tuple(self.draft_perks),
                                 seed=int(self.draft_seed), max_turns=int(self.draft_cap) if self.draft_cap else None)
            except ValueError:
                self.message = 'Seed must be an integer; turn limit must be positive or blank.'
            else:
                self.start(config)
        elif action == 'settings':
            self.settings_return = 'main' if e is None else 'pause'
            if e is not None: e.paused = True
            self.mode = 'settings'
        elif action == 'back_settings':
            self.mode = self.settings_return
        elif action in ('pause', 'resume', 'menu_game'):
            if action == 'menu_game':
                if e is not None: e.paused = True
                self.mode = 'pause'
            elif e is not None and not e.ended:
                self.pause()
        elif action == 'restart' and e is not None:
            speed = e.speed
            self.start(replace(self.config, max_turns=e.max_turns))
            self.engine.speed = speed
        elif action == 'end' and e is not None:
            e.end()
            self.mode = 'game'  # results stay visible; Menu opens result actions
        elif action == 'overview' and r is not None:
            r.overview()
        elif action == 'colony' and r is not None:
            r.focus(e, (r.focus_faction+1) % 4)
        elif action == 'cap' and e is not None and not e.ended:
            self.controls.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t, unicode='t'), e, r)
            self.mode = 'cap'
        elif action in ('apply_cap', 'cancel_cap'):
            key = pygame.K_RETURN if action == 'apply_cap' else pygame.K_ESCAPE
            self.controls.handle(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=''), e, r)
            if self.controls.cap_text is None:
                self.mode = 'pause' if e.paused else 'game'
            else:
                self.message = 'Use a positive turn limit, or leave the field blank.'
        elif action.startswith('speed_') and e is not None:
            e.speed = int(action.split('_')[1])
        elif action.startswith('size_'):
            self.draft_size = int(action.split('_')[1])
        elif action.startswith('faction_'):
            self.selected_faction = int(action.split('_')[1])
        elif action.startswith('perk_'):
            self.draft_perks[self.selected_faction] = action[5:]
        elif action.startswith('fps_'):
            self.fps = int(action.split('_')[1])
        elif action.startswith('text_'):
            self.text_size = int(action.split('_')[1])
            if r is not None: r.font = pygame.font.Font(None, self.text_size)
        elif action.startswith('focus_'):
            value = int(action.split('_')[1])
            self.startup_focus = None if value < 0 else value
            if r is not None: r.startup_focus = self.startup_focus

    def handle(self, event):
        # Some Windows input tools/IMEs emit TEXTINPUT without KEYDOWN. Accept
        # those characters, while suppressing the normal KEYDOWN/TEXTINPUT echo.
        if event.type == pygame.TEXTINPUT:
            echo, self.text_echo = self.text_echo, None
            if echo is not None and echo[0] == event.text and pygame.time.get_ticks()-echo[1] <= 250:
                return
            for character in event.text:
                try:
                    key = pygame.key.key_code(character.lower())
                except ValueError:
                    continue
                self.handle(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=character, text_fallback=True))
            return
        if event.type == pygame.KEYDOWN and getattr(event, 'unicode', '') and not getattr(event, 'text_fallback', False):
            self.text_echo = (event.unicode, pygame.time.get_ticks())
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(800, event.w), max(600, event.h)), pygame.RESIZABLE)
            if self.renderer is not None:
                self.renderer.screen = self.screen
                self.renderer.overlays.viewport_cache.clear()
            return
        if event.type == pygame.WINDOWFOCUSLOST:
            self.controls.drag_button = self.controls.drag_last = None
            if self.active:
                self.engine.paused = True
                self.mode = 'pause'
            return
        if event.type == pygame.KEYDOWN and getattr(event, 'repeat', False) and event.key in (pygame.K_SPACE, pygame.K_ESCAPE):
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and self.mode in ('game','pause','cap'):
            self.pause()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.mode == 'cap': self.action('cancel_cap')
            elif self.mode == 'settings': self.action('back_settings')
            elif self.mode == 'setup': self.action('back_setup')
            elif self.mode in ('game','pause'): self.pause()
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Suppress selection/buttons until a map drag has actually ended.
            if self.controls.drag_button is not None:
                return
            action = next((key for key, rect in self.buttons.items() if rect.collidepoint(event.pos)), None)
            if action:
                self.action(action)
                return
            field = next((key for key, rect in self.fields.items() if rect.collidepoint(event.pos)), None)
            if field:
                self.focused_field, self.selected_text = field, True
                return
            if self.modal_rect is not None and self.modal_rect.collidepoint(event.pos):
                return
            self.focused_field = None
        if self.mode == 'setup' and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.action('start')
            elif event.key == pygame.K_TAB:
                self.focused_field = 'cap' if self.focused_field == 'seed' else 'seed'
                self.selected_text = True
            elif self.focused_field:
                name = 'draft_'+self.focused_field
                text = getattr(self, name)
                if event.key == pygame.K_a and getattr(event, 'mod', 0) & pygame.KMOD_CTRL:
                    self.selected_text = True
                elif event.key == pygame.K_BACKSPACE:
                    setattr(self, name, '' if self.selected_text else text[:-1])
                    self.selected_text = False
                elif getattr(event, 'unicode', '') in '0123456789-' and getattr(event, 'unicode', ''):
                    value = event.unicode
                    updated = ('' if self.selected_text else text)+value
                    if len(updated) < 12 and (value != '-' or self.focused_field == 'seed' and updated == '-'):
                        setattr(self, name, updated)
                        self.selected_text = False
            return
        if self.mode in ('main','setup','settings'):
            return
        e, r = self.engine, self.renderer
        if self.mode == 'cap':
            self.controls.handle(event, e, r)
            if self.controls.request:
                self.action(self.controls.request)
            if self.controls.cap_text is None:
                self.mode = 'pause' if e.paused else 'game'
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.action('restart')
                return
            if event.key == pygame.K_t:
                self.action('cap')
                return
        self.controls.handle(event, e, r)
        if self.controls.request:
            self.action(self.controls.request)

    def frame(self, elapsed, events):
        # Credit only the interval that was actually active. Menus/paused time
        # never enters the engine. Pre-pause debt is retained, not silently lost.
        if self.previous_active:
            self.pending_turns += elapsed*self.previous_speed
        for event in events:
            self.handle(event)
        if self.active and self.running:
            from time import perf_counter
            start = perf_counter()
            self.engine.advance(self.pending_turns/self.engine.speed, max_ticks=1)
            self.pending_turns = 0
            self.last_tick_seconds = perf_counter()-start
        if self.renderer is not None:
            self.renderer.pending_turns = self.pending_turns
        self.previous_active = self.active
        self.previous_speed = self.engine.speed if self.engine is not None else 1

    def draw(self):
        self.buttons, self.fields = {}, {}
        self.modal_rect = None
        if self.engine is not None and self.mode not in ('main','setup','settings'):
            self.renderer.draw(self.engine)
            if self.mode == 'game':
                return
        if self.mode in ('pause','cap'):
            # Compact map-only modal keeps the information panel and inspection
            # accessible, while the simulation is frozen.
            area = self.renderer.geometry(self.engine)[0]
            rect = pygame.Rect(0, 0, min(390, area.w-24), 365 if self.mode == 'pause' else 230)
            rect.center = area.center
            self.modal_rect = rect
            pygame.draw.rect(self.screen, (20, 29, 41), rect, border_radius=12)
            pygame.draw.rect(self.screen, ACCENT, rect, 2, border_radius=12)
            font = pygame.font.Font(None, 27)
            title = 'Final results' if self.engine.ended else ('PAUSED' if self.mode == 'pause' else 'Turn limit')
            self.screen.blit(font.render(title, True, TEXT), (rect.x+24, rect.y+18))
            actions = [('resume','Resume'),('restart','Restart'),('new_game','New Game'),('settings','Settings'),('quit','Quit')]
            if self.mode == 'cap':
                self.screen.blit(font.render((self.controls.cap_text or '')+'_', True, TEXT), (rect.x+24,rect.y+64))
                wrapped(self.screen, pygame.font.Font(None, 20), 'Positive turns or blank for unlimited. Ctrl+A replaces. Space pauses/resumes.', (rect.x+24,rect.y+96),rect.w-48)
                actions=[('apply_cap','Apply'),('cancel_cap','Cancel')]
            for i,(key,label) in enumerate(actions):
                b=pygame.Rect(rect.x+24,rect.y+(68 if self.mode=='pause' else 152)+i*53,rect.w-48,42)
                if self.mode=='cap': b=pygame.Rect(rect.x+24+i*((rect.w-48)//2+4),rect.y+166,(rect.w-56)//2,40)
                enabled=not(key=='resume' and self.engine.ended)
                button(self.screen,font,b,label,enabled=enabled)
                if enabled: self.buttons[key]=b
            return
        canvas = self.menu_canvas
        canvas.fill(BG)
        title = {'main':'ANT COLONIES','setup':'NEW GAME','settings':'SETTINGS'}[self.mode]
        font=pygame.font.Font(None,28)
        heading=pygame.font.Font(None,52)
        canvas.blit(heading.render(title,True,TEXT),(60,42))
        def add(key,label,rect,selected=False):
            self.buttons[key]=pygame.Rect(rect)
            # Mouse conversion is applied below, avoiding false hover at scale.
            factor=min(self.screen.get_width()/1000,self.screen.get_height()/760)
            origin=((self.screen.get_width()-1000*factor)/2,(self.screen.get_height()-760*factor)/2)
            mouse=pygame.mouse.get_pos()
            logical=((mouse[0]-origin[0])/factor,(mouse[1]-origin[1])/factor)
            button(canvas,font,self.buttons[key],label,selected,mouse=logical)
        if self.mode=='main':
            wrapped(canvas,font,'Four colonies. Autonomous workers, soldiers, queens and a changing world.',(60,108),850,MUTED)
            for i,(key,label) in enumerate((('new','New Game'),('settings','Settings'),('quit','Quit'))):
                add(key,label,(300,230+i*95,400,65))
            wrapped(canvas,font,'Choose map size and each faction ability before any simulation time starts.',(150,575),700,MUTED)
        elif self.mode=='setup':
            canvas.blit(font.render('Map size',True,MUTED),(60,110))
            for i,(size,name) in enumerate(((64,'Small'),(128,'Medium'),(256,'Large'),(512,'Huge'))):
                add('size_'+str(size),f'{size} x {size}  {name}',(60+i*222,145,210,48),self.draft_size==size)
            canvas.blit(font.render('Choose a faction, then its ability (duplicates are allowed)',True,MUTED),(60,220))
            for i,name in enumerate(NAMES):
                add('faction_'+str(i),name+': '+self.draft_perks[i].replace('-',' ').title(),(60+i*222,255,210,58),self.selected_faction==i)
                pygame.draw.rect(canvas,COLORS[i],(65+i*222,258,5,51))
            for i,perk in enumerate(PERKS):
                add('perk_'+perk,perk.replace('-',' ').title(),(60+(i%4)*222,350+(i//4)*58,210,48),self.draft_perks[self.selected_faction]==perk)
            wrapped(canvas,font,ABILITIES[self.draft_perks[self.selected_faction]],(60,480),880)
            for i,(field,label,value) in enumerate((('seed','Random seed',self.draft_seed),('cap','Turn limit (blank: unlimited)',self.draft_cap))):
                x=60+i*450
                canvas.blit(font.render(label,True,MUTED),(x,565))
                rect=pygame.Rect(x,597,420,42)
                pygame.draw.rect(canvas,(33,44,59),rect,border_radius=6)
                pygame.draw.rect(canvas,ACCENT if self.focused_field==field else (68,87,104),rect,2,border_radius=6)
                canvas.blit(font.render(value+('|' if self.focused_field==field else ''),True,TEXT),(x+12,607))
                self.fields[field]=rect
            add('back_setup','Back',(60,678,180,48))
            add('start','Start Game',(700,678,240,48),True)
            if self.message: wrapped(canvas,pygame.font.Font(None,21),self.message,(265,680),420,(255,185,125))
        else:
            canvas.blit(font.render('Display rate (simulation speed remains unchanged)',True,MUTED),(60,125))
            for i,value in enumerate((30,60,120)): add('fps_'+str(value),str(value)+' FPS',(60+i*180,165,166,48),self.fps==value)
            canvas.blit(font.render('Information text size',True,MUTED),(60,245))
            for i,value in enumerate((18,20,22)): add('text_'+str(value),str(value)+' px',(60+i*180,285,166,48),self.text_size==value)
            canvas.blit(font.render('Startup camera for the next game or restart',True,MUTED),(60,365))
            for i,(value,label) in enumerate(((-1,'Overview'),(0,'Red'),(1,'Yellow'),(2,'Blue'),(3,'Green'))):
                add('focus_'+str(value),label,(60+i*176,405,164,48),self.startup_focus==(None if value<0 else value))
            wrapped(canvas,font,'Space / Esc: pause menu. Middle or right drag: grab map. Wheel: cursor zoom. Arrows: pan. Home/V: overview. F: colony. S/P/C: overlays. G/H: trail filters. T: turn cap. E: end. R: restart. Scroll the information panel for all statistics.',(60,500),880,MUTED)
            add('back_settings','Back',(60,678,180,48))
        factor=min(self.screen.get_width()/1000,self.screen.get_height()/760)
        width,height=round(1000*factor),round(760*factor)
        x,y=(self.screen.get_width()-width)//2,(self.screen.get_height()-height)//2
        self.screen.fill(BG)
        self.screen.blit(pygame.transform.smoothscale(canvas,(width,height)),(x,y))
        for collection in (self.buttons,self.fields):
            for key,rect in collection.items():
                collection[key]=pygame.Rect(x+round(rect.x*factor),y+round(rect.y*factor),round(rect.w*factor),round(rect.h*factor))
