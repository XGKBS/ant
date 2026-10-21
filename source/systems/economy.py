"""Completed-turn metabolism. Source, friendly supplier, cargo, then signed colony reserve."""
def food_upkeep(population):
    if population < 0:
        raise ValueError('Population cannot be negative')
    q, r = divmod(population, 50)
    return 25*q*(q+1)+r*(q+1)

class Economy:
    def __init__(self, world):
        self.world = world

    def populations(self):
        counts = [0]*4
        for ant in self.world.ants:
            if ant.hp > 0 and ant.kind != 'honeypot':
                counts[ant.faction] += 1
        return counts

    def settle_upkeep(self, turn):
        if not self.world.config.colony_economy_enabled or turn <= 0 or turn % 100:
            return
        members = [[] for _ in self.world.colonies]
        for ant in self.world.ants:
            if ant.hp > 0 and ant.kind != 'honeypot':
                members[ant.faction].append(ant)
        food = self.world.food_system
        sources = {}
        for source in food.sources():
            sources.setdefault(source.position, []).append(source)
        from simulation.spatial import SpatialIndex
        suppliers = SpatialIndex([a for a in self.world.ants if a.kind == 'honeypot' and a.hp > 0])
        for c in self.world.colonies:
            if c.last_upkeep_turn >= turn:
                continue
            personal = source_paid = supplied = 0
            # Faction order, stable ant ID, then nearest supplier / supplier ID.
            for index, ant in enumerate(sorted(members[c.faction], key=lambda a: a.id)):
                required = index//50+1
                remaining = required
                for source in sources.get(ant.position, ()):
                    amount = food.harvest(source, turn, remaining) or 0
                    source_paid += amount;remaining -= amount
                    if not remaining:
                        break
                if remaining:
                    available = sorted((h for h in suppliers.near(ant.position, 10)
                                        if h.faction == ant.faction and h.hp > 0 and h.stored_food > 0),
                                       key=lambda h: (abs(h.position[0]-ant.position[0])+abs(h.position[1]-ant.position[1]), h.id))
                    for supplier in available:
                        amount = min(remaining, supplier.stored_food)
                        supplier.stored_food -= amount
                        supplied += amount;remaining -= amount
                        if not remaining:
                            break
                paid = min(ant.cargo, remaining)
                ant.cargo -= paid
                personal += paid
            cost = food_upkeep(len(members[c.faction]))
            shared = cost-source_paid-supplied-personal
            food.direct_consumed += source_paid
            c.upkeep_source_half += int(2*source_paid)
            c.upkeep_honeypot_half += int(2*supplied)
            c.reserves = (c.reserves_half-int(2*shared))/2
            c.upkeep_spent_half += 2*cost
            c.upkeep_personal_half += int(2*personal)
            c.upkeep_shared_half += int(2*shared)
            c.last_upkeep, c.last_upkeep_turn = cost, turn

    def survive(self, turn):
        if not self.world.config.colony_economy_enabled:
            return
        for c in self.world.colonies:
            if turn <= c.last_economy_turn:
                continue
            c.last_economy_turn = turn
            c.last_healing = c.last_healing_food = 0
            if not c.alive:
                c.starvation_turns = 0
                continue
            # Reproduction and upkeep already settled; never borrow for healing.
            amount = min(2, c.queen.max_hp-c.queen.hp, max(0, c.reserves_half)/2)
            if amount > 0:
                c.queen.hp += amount
                c.reserves = (c.reserves_half-int(amount*2))/2
                c.healing_spent_half += int(amount*2)
                c.last_healing = c.last_healing_food = amount
            if c.reserves < 0:
                c.starvation_turns += 1
                if c.starvation_turns % 2 == 0:
                    c.queen.hp = max(0, c.queen.hp-1)
                    c.starvation_damage += 1
            else:
                c.starvation_turns = 0

    def tick(self, turn):
        self.settle_upkeep(turn)
        self.survive(turn)
