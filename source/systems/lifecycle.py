from simulation.terrain import SOIL

class Lifecycle:
    def __init__(self, world, food):
        self.world, self.food = world, food
        self.ant_deaths = 0

    def hunger(self, turn):
        period = self.world.config.queenless_hunger_period
        for ant in self.world.ants:
            colony = self.world.colonies[ant.faction]
            if ant.hp > 0 and colony.death_turn is not None and turn > colony.death_turn and (turn-colony.death_turn) % period == 0:
                ant.hp = max(0, ant.hp-1)

    def cleanup(self, turn):
        t = self.world.terrain
        survivors = []
        for ant in self.world.ants:
            if ant.hp <= 0:
                t.occupancy[ant.position[1], ant.position[0]] -= 1
                if ant.kind == 'honeypot':
                    amount = ant.stored_food
                    ant.stored_food = 0
                    self.food.drop(ant.position, amount)
                self.food.discarded += ant.cargo
                ant.cargo = 0
                t.deposit(ant.position, ant.soil_cargo)
                ant.soil_cargo = 0
                self.ant_deaths += 1
            else:
                survivors.append(ant)
        self.world.ants = survivors
        for colony in self.world.colonies:
            if colony.queen.hp <= 0 and colony.death_turn is None:
                colony.queen.hp = 0
                colony.death_turn = turn
                colony.threat, colony.threat_target = 'queenless', None
                colony.strategic_state, colony.reserve_target = 'Peace', 0
                colony.critical_turns = colony.quiet_turns = 0
                colony.declaration_target = None
                colony.saving_upgrade = False
                colony.bonus_queue.clear()
                colony.greed_seen.clear()
                colony.greed_credits.clear()
                for x, y in colony.queen.footprint:
                    t.set(x, y, SOIL)
                    if (x, y) not in self.world.food_candidates:
                        self.world.food_candidates.append((x, y))
                self.food.trophy(colony)
                for ant in self.world.ants:
                    if ant.faction != colony.faction:
                        continue
                    # Perk-derived capacity drops immediately; excess is recorded as waste.
                    excess = max(0, ant.cargo-1)
                    self.food.discarded += excess
                    ant.cargo -= excess
                    if ant.cargo + ant.soil_cargo > 1:
                        t.deposit(ant.position, ant.soil_cargo)
                        ant.soil_cargo = 0
                    ant.order_state, ant.order_target, ant.order_epoch = 'Peace', None, -1
                    ant.route.clear()

    def winner(self):
        living = [c for c in self.world.colonies if c.alive]
        if len(living) == 1:
            return living[0].faction
        return None

    def all_queens_dead(self):
        return not any(c.alive for c in self.world.colonies)
