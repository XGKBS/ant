from dataclasses import dataclass, field

@dataclass
class Ant:
    id: int
    faction: int
    position: tuple[int, int]
    hp: float | None = None
    state: str = 'explore'
    heading: tuple[int, int] = (1, 0)
    cargo: float = 0
    action_used: bool = False
    path: list = field(default_factory=list)
    kind: str = 'worker'
    target: tuple[int, int] | None = None
    food_id: int | None = None
    known_food: dict = field(default_factory=dict)
    visits: dict = field(default_factory=dict)
    route: list = field(default_factory=list)
    route_goal: tuple[int, int] | None = None
    route_revision: int = -1
    blocked_turns: int = 0
    dig_target: tuple[int, int] | None = None
    last_action: str | None = None
    last_action_turn: int = -1
    food_distance: int = 0
    trail_visits: dict = field(default_factory=dict)
    foreign_signal: bool = False
    foreign_target: tuple[int, int] | None = None
    ignored_food: dict = field(default_factory=dict)
    combat_target: tuple[str, int] | None = None
    planned_budget: int = 2
    pending_report: tuple[int, int] | None = None
    reported_signals: set = field(default_factory=set)
    soil_cargo: int = 0
    construction_task: int | None = None
    station_empty_until: dict = field(default_factory=dict)
    navigation_status: str = 'ready'
    route_chunks: dict = field(default_factory=dict)
    station_commit_until: int = 0
    order_epoch: int = -1
    order_state: str = 'Peace'
    order_target: tuple[int, int] | None = None
    cargo_origin: str = 'harvest'
    depot_id: int | None = None
    depot_memory: dict = field(default_factory=dict)
    food_observations: dict = field(default_factory=dict)
    stored_food: float = 0
    honeypot_id: int | None = None
    escort_id: int | None = None
    escort_target: tuple[int, int] | None = None
    exploration_target: tuple[int, int] | None = None
    exploration_until: int = 0
    information: dict = field(default_factory=dict)
    information_seen: dict = field(default_factory=dict)
    last_information_turn: int = -1
    idle_target: tuple | None = None
    idle_until: int = 0
    idle_role: str = ''
    surveyed_chunks: set = field(default_factory=set)
    moved_this_turn: bool = False
    activity: str = 'waiting_dependency'
    stationary_turns: int = 0
    unproductive_idle_turns: int = 0

    def __post_init__(self):
        if self.kind not in ('worker', 'soldier', 'honeypot'):
            raise ValueError('Ant kind must be worker, soldier or honeypot')
        if (self.stored_food < 0 or self.stored_food > 10 or self.stored_food*2 != int(self.stored_food*2)
                or self.kind != 'honeypot' and self.stored_food
                or self.kind == 'honeypot' and (self.cargo or self.soil_cargo)):
            raise ValueError('Honeypot storage must be exact half-units in [0,10], separate from cargo')
        if self.hp is None:
            self.hp = self.max_hp

    @property
    def max_hp(self):
        return 15 if self.kind == 'honeypot' else (12 if self.kind == 'soldier' else 5)

    @property
    def damage(self):
        return 0 if self.kind == 'honeypot' else (3 if self.kind == 'soldier' else 1)

@dataclass
class Queen:
    id: int
    faction: int
    position: tuple[int, int]
    hp: float = 50
    damage: int = field(default=0, init=False)
    last_attacked_turn: int = -1000000
    max_hp: float = field(init=False)

    def __post_init__(self):
        # Existing queen HP default is the canonical cap, even for wounded fixtures.
        self.max_hp = type(self).__dataclass_fields__['hp'].default

    @property
    def footprint(self):
        x, y = self.position
        return [(x + dx, y + dy) for dy in range(2) for dx in range(2)]

@dataclass
class Colony:
    faction: int
    queen: Queen
    reserves: float = 0
    perk: str = 'production'
    upgraded: bool = False
    death_turn: int | None = None
    threat: str = 'safe'
    threat_target: tuple[int, int] | None = None
    soldier_credit: int = 0
    produced_workers: int = 0
    produced_soldiers: int = 0
    produced_honeypots: int = 0
    post_upgrade_counts: dict = field(default_factory=lambda: {'worker': 0, 'soldier': 0})
    bonus_queue: list = field(default_factory=list)
    bonus_births: int = 0
    spent_half: int = 0
    upgrade_spent_half: int = 0
    received_half: int = 0
    greed_seen: dict = field(default_factory=dict)
    greed_credits: dict = field(default_factory=dict)
    last_attacked_turn: int = -1000000
    last_attack_position: tuple[int, int] | None = None
    last_birth_turn: int = -1
    last_queen_action_turn: int = -1
    report_turn: int = -1000000
    report_position: tuple[int, int] | None = None
    saving_upgrade: bool = False
    strategic_state: str = 'Peace'
    reserve_target: int = 10
    critical_turns: int = 0
    quiet_turns: int = 0
    last_strategy_turn: int = 0
    declaration_epoch: int = 0
    declaration_target: tuple[int, int] | None = None
    depot_spent_half: int = 0
    upkeep_spent_half: int = 0
    upkeep_source_half: int = 0
    upkeep_honeypot_half: int = 0
    upkeep_personal_half: int = 0
    upkeep_shared_half: int = 0
    healing_spent_half: int = 0
    last_upkeep_turn: int = 0
    last_upkeep: int = 0
    last_economy_turn: int = 0
    starvation_turns: int = 0
    starvation_damage: int = 0
    last_healing: float = 0
    last_healing_food: float = 0

    @property
    def alive(self):
        return self.death_turn is None and self.queen.hp > 0

    @property
    def active_perk(self):
        return self.perk if self.alive else None

    @property
    def reserves_half(self):
        value = self.reserves * 2
        if value != int(value):
            raise ValueError('Reserves must be exact signed half-units')
        return int(value)

@dataclass
class Food:
    id: int
    position: tuple[int, int]
    tier: str
    units: float
    max_scent: int
    age: int = 0
    respawn_deadline: int | None = None
    generation: int = 0

@dataclass
class SupplyStation(Food):
    origin_faction: int = 0  # placement context only; never ownership
    intended: tuple[int, int] = (0, 0)
    placement_reason: str = 'exact offset'
    next_refill: int = 25
    generated_units: int = 0
    collected_units: float = 0
    last_refill_units: int = 0


@dataclass
class Depot:
    id: int
    faction: int
    position: tuple[int, int]
    dimensions: tuple[int, int] = (2, 2)
    deposited: float = 0  # cumulative receipts only, never an inventory

    @property
    def footprint(self):
        x, y = self.position
        return tuple((x+dx, y+dy) for dy in range(self.dimensions[1]) for dx in range(self.dimensions[0]))
