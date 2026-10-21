import numpy as np

BASE, FOOD, BATTLE = 0, 1, 2

class Pheromones:
    """Dense faction/channel lookup, sparse decay of active cells only."""
    def __init__(self, config):
        self.config = config
        self.values = np.zeros((4, 3, config.size, config.size), dtype=np.float32)
        self.active = set()

    def reinforce(self, faction, channel, position, strength):
        x, y = position
        key = faction, channel, y, x
        self.values[key] = min(20.0, max(float(self.values[key]), strength) + self.config.pheromone_reinforcement)
        self.active.add(key)

    def decay(self):
        for key in tuple(self.active):
            value = float(self.values[key]) * self.config.pheromone_decay
            if value < self.config.pheromone_cutoff:
                self.values[key] = 0
                self.active.remove(key)
            else:
                self.values[key] = value

    def read(self, faction, channel, position):
        x, y = position
        return float(self.values[faction, channel, y, x])

    def foreign_presence(self, faction, position):
        x, y = position
        return any(np.any(self.values[other, :, y, x] > 0) for other in range(4) if other != faction)

    def sense_foreign(self, faction, position, radius):
        """Return nearest foreign presence, without interpreting its channel/strength."""
        x, y = position
        n = self.config.size
        left, top = max(0, x-radius), max(0, y-radius)
        right, bottom = min(n, x+radius+1), min(n, y+radius+1)
        presence = np.any(self.values[:, :, top:bottom, left:right] > 0, axis=1)
        presence[faction] = False
        yy, xx = np.ogrid[top:bottom, left:right]
        mask = (np.abs(xx-x)+np.abs(yy-y)) <= radius
        rows, columns = np.nonzero(np.any(presence, axis=0) & mask)
        points = [(int(cx)+left, int(cy)+top) for cy, cx in zip(rows, columns)]
        return min(points, key=lambda p: (abs(p[0]-x)+abs(p[1]-y), p)) if points else None

    def foreign_near(self, faction, queen, radius):
        x, y = queen.position
        n = self.config.size
        left, top = max(0, x-radius), max(0, y-radius)
        right, bottom = min(n, x+2+radius), min(n, y+2+radius)
        yy, xx = np.ogrid[top:bottom, left:right]
        dist = np.maximum(x-xx, 0) + np.maximum(xx-(x+1), 0) + np.maximum(y-yy, 0) + np.maximum(yy-(y+1), 0)
        mask = dist <= radius
        return any(np.any(self.values[other, :, top:bottom, left:right][:, mask] > 0)
                   for other in range(4) if other != faction)
