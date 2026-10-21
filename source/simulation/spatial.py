from collections import defaultdict
from ai.pathfinding import distance

class SpatialIndex:
    def __init__(self, ants, bucket_size=8):
        self.bucket_size = bucket_size
        self.buckets = defaultdict(list)
        for ant in ants:
            if ant.hp > 0:
                x, y = ant.position
                self.buckets[x//bucket_size, y//bucket_size].append(ant)

    def near(self, position, radius):
        x, y = position
        b = self.bucket_size
        for cy in range((y-radius)//b, (y+radius)//b+1):
            for cx in range((x-radius)//b, (x+radius)//b+1):
                for ant in self.buckets.get((cx, cy), ()):
                    if ant.hp > 0 and distance(position, ant.position) <= radius:
                        yield ant

    def near_limited(self, position, radius, limit, offset=0):
        """Stable rotating spatial probes with a hard examined-entry bound."""
        x,y=position;b=self.bucket_size;examined=0
        keys=[(cx,cy) for cy in range((y-radius)//b,(y+radius)//b+1)
              for cx in range((x-radius)//b,(x+radius)//b+1)]
        start=offset%len(keys)
        for key in keys[start:]+keys[:start]:
            bucket=self.buckets.get(key,())
            if not bucket:continue
            first=(offset//len(keys))%len(bucket)
            for index in range(min(len(bucket),limit-examined)):
                ant=bucket[(first+index)%len(bucket)];examined+=1
                if ant.hp>0 and distance(position,ant.position)<=radius:yield ant
            if examined>=limit:return
