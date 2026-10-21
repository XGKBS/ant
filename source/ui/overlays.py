"""Read-only, tick-cached visualizations. No simulation module imports this file."""
from dataclasses import dataclass
import numpy as np
import pygame
from config import COLORS

LAYERS = ('scent', 'pheromones', 'territory')
CHANNELS = ('Base', 'Food', 'Battle')

@dataclass(frozen=True)
class InfluenceStyle:
    ant_radius: int = 6
    queen_radius: int = 12
    worker_weight: float = 1
    soldier_weight: float = 2
    queen_weight: float = 4
    pheromone_weight: float = .1
    neutral_threshold: float = .25
    contested_ratio: float = .85

def rgba_surface(array):
    # Copy: the surface must not retain a mutable simulation/temporary buffer.
    h, w = array.shape[:2]
    surface = pygame.image.frombuffer(array.tobytes(), (w, h), 'RGBA')
    # Native display channel layout enables SDL's fast alpha blitter. Keeping
    # RGBA byte order would convert channels again on every viewport blit.
    return surface.convert_alpha() if pygame.display.get_surface() is not None else surface.copy()

def influence(engine, style=InfluenceStyle()):
    """Completed logical positions, live queens/activity and actual chemicals.

    Manhattan proximity is an observational estimate, not route reachability.
    All radii/weights are presentation defaults and never consult queen perks.
    """
    world = engine.world
    n = world.config.size
    scores = np.zeros((4, n, n), dtype=np.float32)
    r = style.ant_radius
    yy, xx = np.ogrid[-r:r+1, -r:r+1]
    kernel = np.maximum(0, 1-(np.abs(xx)+np.abs(yy))/(r+1)).astype(np.float32)
    for ant in world.ants:
        if ant.hp <= 0:
            continue
        x, y = ant.position
        l, t, right, b = max(0, x-r), max(0, y-r), min(n, x+r+1), min(n, y+r+1)
        weight = style.soldier_weight if ant.kind == 'soldier' else style.worker_weight
        scores[ant.faction, t:b, l:right] += weight*kernel[t-y+r:b-y+r, l-x+r:right-x+r]
    for colony in world.colonies:
        f = colony.faction
        p = engine.pheromones.values[f]
        scores[f] += style.pheromone_weight*(p[0]+p[1]+2*p[2])
        if colony.alive:
            x, y = colony.queen.position
            r = style.queen_radius
            l, t, right, b = max(0, x-r), max(0, y-r), min(n, x+2+r), min(n, y+2+r)
            yy, xx = np.ogrid[t:b, l:right]
            d = np.maximum(x-xx, 0)+np.maximum(xx-x-1, 0)+np.maximum(y-yy, 0)+np.maximum(yy-y-1, 0)
            activity = min(2, colony.received_half/20) + min(2, (colony.produced_workers+colony.produced_soldiers)/10)
            scores[f, t:b, l:right] += (style.queen_weight+activity)*np.maximum(0, 1-d/(r+1))
    scores[:, world.terrain.capacity == 0] = 0
    owner = np.argmax(scores, axis=0).astype(np.int8)
    top = np.max(scores, axis=0)
    second = np.partition(scores, 2, axis=0)[2]
    owner[(second >= style.neutral_threshold) & (second >= style.contested_ratio*top)] = -2
    owner[top < style.neutral_threshold] = -1
    return scores, owner

class Overlays:
    """One raster per enabled layer/tick, one viewport cache per layer.

    Zoomed pheromones use a 4-column (faction) × 3-row (channel) cell glyph.
    Overview uses a weighted color mix with peak-strength opacity. Faction and
    channel filters resolve blends without omitting any AI data from the model.
    """
    def __init__(self, style=InfluenceStyle()):
        self.enabled = dict.fromkeys(LAYERS, False)
        self.faction = None
        self.channel = None
        self.style = style
        self.menu_open = True
        self.builds = dict.fromkeys(LAYERS, 0)
        self.invalidate()

    def invalidate(self):
        self.world = None
        self.keys, self.surfaces, self.viewport_cache = {}, {}, {}
        self.scent_values = self.territory_scores = self.territory_owner = None
        self.detail = None
        self.detail_key = None
        self.detail_origin = (0, 0)

    def toggle(self, name):
        if name not in self.enabled:
            raise ValueError('Unknown overlay')
        self.enabled[name] = not self.enabled[name]

    def cycle_faction(self):
        self.faction = 0 if self.faction is None else (self.faction+1 if self.faction < 3 else None)

    def cycle_channel(self):
        self.channel = 0 if self.channel is None else (self.channel+1 if self.channel < 2 else None)

    def prepare(self, engine, detail=False, detail_bounds=None):
        if self.world is not engine.world:
            self.invalidate()
            self.world = engine.world
        base_key = (engine.turn, engine.world.terrain.revision)
        for name in LAYERS:
            if not self.enabled[name]:
                continue
            key = base_key + ((self.faction, self.channel) if name == 'pheromones'
                              else (self.style,) if name == 'territory' else ())
            if self.keys.get(name) != key:
                getattr(self, '_'+name)(engine)
                self.keys[name] = key
                self.viewport_cache.pop(name, None)
                self.builds[name] += 1
        key = (self.keys.get('pheromones'), detail_bounds)
        if self.enabled['pheromones'] and detail and self.detail_key != key:
            self._pheromone_detail(engine, detail_bounds)
            self.detail_key = key
            self.viewport_cache.pop('pheromones', None)

    def _scent(self, engine):
        n = engine.world.config.size
        values = np.zeros((n, n), dtype=np.float32)
        for (x, y), value in engine.food.scent.items():
            values[y, x] = value
        rgba = np.zeros((n, n, 4), dtype=np.uint8)
        rgba[:, :, :3] = (65, 225, 245)
        rgba[:, :, 3] = np.where(values > 0, 30+170*np.clip(values, 0, 1), 0).astype(np.uint8)
        self.scent_values = values
        self.surfaces['scent'] = rgba_surface(rgba)

    def _pheromones(self, engine):
        values = engine.pheromones.values
        n = engine.world.config.size
        factions = range(4) if self.faction is None else (self.faction,)
        channels = range(3) if self.channel is None else (self.channel,)
        total = np.zeros((n, n), dtype=np.float32)
        peak = np.zeros_like(total)
        rgb = np.zeros((n, n, 3), dtype=np.float32)
        for f in factions:
            strength = np.zeros_like(total)
            for channel in channels:
                strength += values[f, channel]
                np.maximum(peak, values[f, channel], out=peak)
            total += strength
            for component in range(3):
                rgb[:, :, component] += strength*COLORS[f][component]
        np.divide(rgb, total[:, :, None], out=rgb, where=total[:, :, None] > 0)
        rgba = np.zeros((n, n, 4), dtype=np.uint8)
        rgba[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        rgba[:, :, 3] = (220*np.sqrt(np.clip(peak/20, 0, 1))).astype(np.uint8)
        self.surfaces['pheromones'] = rgba_surface(rgba)

    def _pheromone_detail(self, engine, bounds=None):
        n = engine.world.config.size
        left, top, right, bottom = bounds if bounds is not None else (0, 0, n, n)
        width, height = right-left, bottom-top
        rgba = np.zeros((height, 3, width, 4, 4), dtype=np.uint8)
        for f in range(4):
            for c in range(3):
                if self.faction is not None and f != self.faction or self.channel is not None and c != self.channel:
                    continue
                rgba[:, c, :, f, :3] = COLORS[f]
                values = engine.pheromones.values[f, c, top:bottom, left:right]
                rgba[:, c, :, f, 3] = (220*np.sqrt(np.clip(values/20, 0, 1))).astype(np.uint8)
        self.detail = rgba_surface(rgba.reshape(height*3, width*4, 4))
        self.detail_origin = left, top

    def _territory(self, engine):
        scores, owner = influence(engine, self.style)
        n = engine.world.config.size
        rgba = np.zeros((n, n, 4), dtype=np.uint8)
        for f in range(4):
            rgba[owner == f, :3] = COLORS[f]
        rgba[:, :, 3] = np.where(owner >= 0, np.minimum(145, 45+15*np.max(scores, axis=0)), 0).astype(np.uint8)
        yy, xx = np.indices((n, n))
        contested = owner == -2
        rgba[contested, :3] = np.where(((xx+yy) % 2)[contested, None], (205, 205, 225), (140, 140, 160))
        rgba[contested, 3] = 125
        self.territory_scores, self.territory_owner = scores, owner
        self.surfaces['territory'] = rgba_surface(rgba)

    def draw(self, screen, engine, scale, origin, bounds):
        left, top, right, bottom = bounds
        self.prepare(engine, detail=scale >= 4 and right > left and bottom > top, detail_bounds=bounds)
        if right <= left or bottom <= top:
            return
        destination = (round(origin[0]+left*scale), round(origin[1]+top*scale))
        dimensions = (max(1, round((right-left)*scale)), max(1, round((bottom-top)*scale)))
        # Territory wash, scent field, then fine pheromones; entities stay above.
        for name in ('territory', 'scent', 'pheromones'):
            if not self.enabled[name]:
                continue
            detailed = name == 'pheromones' and scale >= 4
            source = self.detail if detailed else self.surfaces[name]
            rx, ry = (4, 3) if detailed else (1, 1)
            key = (self.keys[name], detailed, bounds, dimensions)
            old = self.viewport_cache.get(name)
            if old is None or old[0] != key:
                ox, oy = self.detail_origin if detailed else (0, 0)
                crop = source.subsurface(((left-ox)*rx, (top-oy)*ry, (right-left)*rx, (bottom-top)*ry))
                scaled = pygame.transform.scale(crop, dimensions)
                self.viewport_cache[name] = key, scaled
            screen.blit(self.viewport_cache[name][1], destination)

    def cache_bytes(self):
        objects = list(self.surfaces.values()) + [v[1] for v in self.viewport_cache.values()]
        objects += [self.detail, self.scent_values, self.territory_scores, self.territory_owner]
        total, seen = 0, set()
        for obj in objects:
            if obj is None or id(obj) in seen:
                continue
            seen.add(id(obj))
            total += obj.nbytes if isinstance(obj, np.ndarray) else obj.get_pitch()*obj.get_height()
        return total
