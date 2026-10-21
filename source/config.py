from dataclasses import dataclass

COLORS = ((225, 65, 65), (235, 205, 55), (70, 140, 245), (65, 205, 110))
PERKS = ('production', 'exploration', 'warfare', 'speed', 'blitz', 'greed', 'heavy-lifting', 'sensitivity')

@dataclass(frozen=True)
class Config:
    size: int = 512
    seed: int = 7
    max_turns: int | None = None
    stone_density: float = 0.025
    large_stone_density: float = 0.002
    nest_clearance: int = 5
    food_count: int = 24
    colony_economy_enabled: bool = True
    supply_stations_enabled: bool = True
    pheromone_decay: float = 0.96
    pheromone_reinforcement: float = 0.25
    pheromone_cutoff: float = 0.01
    path_search_limit: int = 4096
    navigation_node_budget: int = 65536
    navigation_cache_fields: int = 48
    navigation_queue_limit: int = 64
    navigation_quantum: int = 256
    station_commit_turns: int = 4
    cooperative_threshold: int = 128
    cooperative_batches: int = 8
    cooperative_batch_size: int = 32
    congestion_turns: int = 2
    busy_path_visits: int = 8
    food_spacing: int = 5
    respawn_delay: int = 25
    center_radius_fraction: float = 1/6
    failed_target_cooldown: int = 25
    micro_respawn_tier: str | None = 'micro'
    perks: tuple[str, ...] = ('production', 'exploration', 'warfare', 'speed')
    strategic_reserves_enabled: bool = True
    strategic_reserve_min: int = 10
    strategic_reserve_per_ant: float = 0.5
    total_war_threat_turns: int = 5
    total_war_hp_fraction: float = 0.30
    total_war_recovery_turns: int = 10
    communication_radius: int = 2
    information_interval: int = 4
    information_capacity: int = 12
    information_probe_limit: int = 16
    information_peers: int = 2
    information_messages_per_ant: int = 2
    information_events_per_turn: int = 128
    idle_planning_interval: int = 8
    idle_population_threshold: int = 1000
    idle_assignments_per_turn: int = 8
    idle_path_retries_per_turn: int = 4
    war_logistics_fraction: float = 0.25
    depots_enabled: bool = True
    depot_food_cost: int = 15
    depot_footprint: tuple[int, int] = (2, 2)
    depot_min_spacing: int = 6
    depot_home_distance: int = 4
    depot_proposal_interval: int = 10
    depot_food_radius: int = 8
    depot_min_sources: int = 1
    depot_delivery_saving: int = 2
    depot_builder_limit: int = 4
    depot_savings_turns: int = 150
    depot_candidate_limit: int = 12
    honeypots_enabled: bool = True
    honeypot_workers_per_unit: int = 20
    honeypot_min_workers: int = 6
    honeypot_follow_radius: int = 10
    honeypot_drop_scent: int = 4
    drop_placement_budget: int = 256
    exploration_enabled: bool = True
    exploration_start_turn: int = 10
    expedition_fraction: float = 0.20
    exploration_chunk: int = 8
    exploration_commit_turns: int = 24
    reproduction_enabled: bool = True
    combat_enabled: bool = True
    combat_range: int = 1
    queen_alarm_radius: int = 10
    near_base_radius: int = 5
    critical_queen_hp: int = 15
    attack_memory_turns: int = 3
    queenless_hunger_period: int = 5
    trophy_units: int = 50
    trophy_scent: int = 24
    upgrade_cost_half: int = 20
    upgrade_save_worker_threshold: int = 8
    soldier_percentages: tuple[int, ...] = (0, 25, 50, 75, 100)
    construction_enabled: bool = True
    ordinary_stone_weight: int = 4
    large_stone_weight_per_cell: int = 4
    stone_min_load_ratio: float = 0.5
    stone_min_speed_ratio: float = 0.25
    stone_base_speed: float = 1.0
    stone_work_radius: int = 2
    construction_radius: int = 6
    construction_fraction: float = 0.5
    construction_timeout: int = 30
    construction_cooldown: int = 5
    composition_soil: int = 5
    composition_max_cells: int = 16
    composition_max_gap: int = 0
    composition_min_shared_edges: int = 1
    composition_access_radius: int = 2
    max_soil_layers: int = 3

    def __post_init__(self):
        if min(self.information_interval,self.information_capacity,self.information_probe_limit,
               self.information_peers,self.information_messages_per_ant,self.information_events_per_turn,
               self.idle_planning_interval,self.idle_population_threshold,self.idle_assignments_per_turn,
               self.idle_path_retries_per_turn)<1:
            raise ValueError('Information and low-priority planning bounds must be positive')
        if self.depot_food_cost != 15 or self.depot_builder_limit < 2 or min(self.depot_savings_turns, self.depot_candidate_limit) < 1:
            raise ValueError("Depot V2 requires exactly 15 food and positive planning bounds")
        if (min(self.honeypot_workers_per_unit, self.honeypot_min_workers, self.honeypot_follow_radius,
                self.honeypot_drop_scent, self.drop_placement_budget, self.exploration_chunk,
                self.exploration_commit_turns) < 1 or self.exploration_start_turn < 0
                or not 0 < self.expedition_fraction < 1):
            raise ValueError('Invalid supply/exploration configuration')
        if (self.strategic_reserve_min < 0 or self.strategic_reserve_per_ant < 0
                or min(self.total_war_threat_turns, self.total_war_recovery_turns, self.communication_radius,
                       self.depot_food_cost, self.depot_min_spacing, self.depot_home_distance,
                       self.depot_proposal_interval, self.depot_food_radius, self.depot_min_sources) < 1
                or not 0 < self.total_war_hp_fraction <= 1 or not 0 < self.war_logistics_fraction <= 1
                or len(self.depot_footprint) != 2 or min(self.depot_footprint) < 1):
            raise ValueError('Invalid strategic/depot configuration')
        if min(self.navigation_node_budget,self.navigation_cache_fields,self.navigation_queue_limit,
               self.navigation_quantum,self.cooperative_threshold,self.cooperative_batches,self.cooperative_batch_size) < 1:
            raise ValueError('Navigation/execution budgets must be positive')
        if (min(self.ordinary_stone_weight, self.large_stone_weight_per_cell, self.stone_base_speed) <= 0
                or self.stone_base_speed > 1
                or not 0 < self.stone_min_load_ratio < 1 or not 0 < self.stone_min_speed_ratio <= 1
                or min(self.stone_work_radius, self.construction_radius, self.construction_timeout, self.composition_soil,
                       self.construction_cooldown, self.composition_min_shared_edges, self.composition_access_radius) < 1
                or not 0 < self.construction_fraction <= 1 or self.max_soil_layers != 3
                or self.composition_max_cells < 2 or self.composition_max_gap != 0):
            raise ValueError('Invalid construction configuration; composition uses a shared cardinal seam')
        if self.size < 32:
            raise ValueError('Map size must be at least 32')
        if self.max_turns is not None and self.max_turns <= 0:
            raise ValueError('Turn cap must be positive or omitted')
        if not 0 < self.pheromone_decay < 1:
            raise ValueError('Pheromone decay must be between zero and one')
        if self.food_count < 0 or self.food_spacing < 1 or self.respawn_delay < 1:
            raise ValueError('Invalid food configuration')
        if self.micro_respawn_tier not in ('micro', None):
            raise ValueError('Micro sources may renew as micro or remain exhausted')
        if len(self.perks) != 4 or any(p not in PERKS for p in self.perks):
            raise ValueError('Choose exactly four valid perks, one per faction')
        if self.combat_range < 0 or self.queenless_hunger_period < 1 or self.trophy_units <= 0:
            raise ValueError('Invalid combat/survival configuration')
        if len(self.soldier_percentages) != 5 or any(not 0 <= p <= 100 for p in self.soldier_percentages):
            raise ValueError('Five soldier percentages in [0,100] required')
        if self.upgrade_save_worker_threshold < 1 or self.upgrade_cost_half < 1 or int(self.upgrade_cost_half) != self.upgrade_cost_half:
            raise ValueError('Upgrade thresholds and integer half-unit cost must be positive')
