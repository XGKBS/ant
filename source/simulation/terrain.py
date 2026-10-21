import numpy as np

SOIL, PASSAGE, STONE, LARGE_STONE, NEST, REINFORCED = range(6)

class Terrain:
    def __init__(self, size):
        self.cells = np.zeros((size, size), dtype=np.uint8)
        self.capacity = np.ones((size, size), dtype=np.uint8)
        self.occupancy = np.zeros((size, size), dtype=np.uint8)
        self.excavated_units = 0
        self.revision = 0
        self.topology_revision = 0
        self.topology_versions = np.zeros((size, size), dtype=np.uint64)
        self.navigation_chunks = np.zeros(((size+15)//16,(size+15)//16),dtype=np.uint64)
        self.traffic = np.zeros((size, size), dtype=np.uint32)
        # Substrate remains underneath stones/nests. Set is a geometry primitive;
        # physical transfers go through dig/fill, never through geometry painting.
        self.layers = np.ones((size, size), dtype=np.uint8)
        self.loose_soil = {}  # sparse ground stores: position -> whole units
        self.stone_ids = np.full((size, size), -1, dtype=np.int32)

    def set(self, x, y, kind):
        was_traversable = bool(self.capacity[y, x])
        self.cells[y, x] = kind
        self.capacity[y, x] = 4 if kind == PASSAGE else (1 if kind in (SOIL, REINFORCED) else 0)
        self.revision += 1
        if was_traversable != bool(self.capacity[y, x]):
            self.topology_revision += 1
            self.topology_versions[y, x] = self.topology_revision
            self.navigation_chunks[y//16,x//16] = self.topology_revision

    def topology_version_near(self, position, radius):
        """Conservative dependency box for a cardinal field with a bounded radius."""
        x, y = position
        h, w = self.capacity.shape
        return int(self.topology_versions[max(0, y-radius):min(h, y+radius+1),
                                          max(0, x-radius):min(w, x+radius+1)].max(initial=0))

    def dig(self, x, y):
        h, w = self.cells.shape
        if not (0 <= x < w and 0 <= y < h):
            return False
        if self.cells[y, x] != SOIL or self.layers[y, x] != 1:
            return False
        self.set(x, y, PASSAGE)
        self.layers[y, x] = 0
        self.deposit((x, y), 1)
        self.excavated_units += 1
        return True

    def deposit(self, position, units):
        if units < 0 or int(units) != units:
            raise ValueError('Soil uses nonnegative whole units')
        if units:
            self.loose_soil[position] = self.loose_soil.get(position, 0) + units

    def withdraw(self, position, units=1):
        if units <= 0 or int(units) != units or self.loose_soil.get(position, 0) < units:
            return False
        self.loose_soil[position] -= units
        if not self.loose_soil[position]:
            del self.loose_soil[position]
        return True

    def strength(self, position):
        x, y = position
        return int(self.layers[y, x])**2

    def fill(self, position, maximum=3, carrier=None):
        x, y = position
        h, w = self.cells.shape
        if not (0 <= x < w and 0 <= y < h):
            return False
        if (self.cells[y, x] not in (SOIL, PASSAGE, REINFORCED)
                or self.layers[y, x] >= min(3, maximum) or self.occupancy[y, x] > 1):
            return False
        if carrier is None:
            if not self.withdraw(position):
                return False
        elif carrier.soil_cargo < 1:
            return False
        else:
            carrier.soil_cargo -= 1
        self.layers[y, x] += 1
        self.set(x, y, REINFORCED)
        return True

    def available(self, x, y):
        h, w = self.cells.shape
        return 0 <= x < w and 0 <= y < h and self.occupancy[y, x] < self.capacity[y, x]
