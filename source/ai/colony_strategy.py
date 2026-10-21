from ai.pathfinding import distance
from systems.perks import queen_sensing
from systems.strategy import update_reserves

LEVELS = ('safe', 'alert', 'contact', 'near-base', 'critical')

class ColonyStrategy:
    def __init__(self, world, combat, pheromones):
        self.world, self.combat, self.pheromones = world, combat, pheromones

    def assess(self, turn):
        update_reserves(self.world)
        for colony in self.world.colonies:
            if not colony.alive:
                colony.threat, colony.threat_target = 'queenless', None
                colony.strategic_state, colony.critical_turns, colony.quiet_turns = 'Peace', 0, 0
                colony.declaration_target = None
                continue
            queen = colony.queen
            radius = queen_sensing(colony, self.world.config)
            enemies = {a.id: a for p in queen.footprint for a in self.combat.index.near(p, radius) if a.faction != colony.faction}
            level, target = 0, None
            if self.pheromones.foreign_near(colony.faction, queen, radius):
                level = 1
            if turn-colony.report_turn <= self.world.config.attack_memory_turns:
                level, target = 1, colony.report_position
            if enemies:
                nearest = min(enemies.values(), key=lambda a: (min(distance(a.position, p) for p in queen.footprint), a.id))
                nearest_distance = min(distance(nearest.position, p) for p in queen.footprint)
                level, target = 2, nearest.position
                if nearest_distance <= self.world.config.near_base_radius:
                    level = 3
                if nearest_distance <= self.world.config.combat_range or queen.hp <= self.world.config.critical_queen_hp:
                    level = 4
            if turn-colony.last_attacked_turn <= self.world.config.attack_memory_turns:
                level = max(level, 2)
                target = target or colony.last_attack_position
            if turn-queen.last_attacked_turn <= self.world.config.attack_memory_turns:
                level, target = 4, target or colony.last_attack_position
            colony.threat, colony.threat_target = LEVELS[level], target

            # assess() also runs during planning; count each completed turn once.
            if turn > colony.last_strategy_turn:
                consecutive = turn == colony.last_strategy_turn+1
                colony.critical_turns = (colony.critical_turns if consecutive else 0)+1 if level == 4 else 0
                colony.quiet_turns = (colony.quiet_turns if consecutive else 0)+1 if level < 2 else 0
                colony.last_strategy_turn = turn
                urgent = bool(enemies) and queen.hp < queen.max_hp*self.world.config.total_war_hp_fraction
                state = colony.strategic_state
                if colony.critical_turns >= self.world.config.total_war_threat_turns or urgent:
                    state = 'Total War'
                elif state == 'Total War' and colony.quiet_turns < self.world.config.total_war_recovery_turns:
                    pass
                else:
                    state = 'Alert' if level else 'Peace'
                # A changed, actually observed target is a new physical message too.
                message_target = target if state == 'Total War' else None
                if state != colony.strategic_state or message_target != colony.declaration_target:
                    colony.declaration_epoch += 1
                    colony.declaration_target = message_target
                colony.strategic_state = state
