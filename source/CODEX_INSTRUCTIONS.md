# CODEX_INSTRUCTIONS — Ant Colony Simulation V1.3

You are implementing a complete, modular, autonomous four-faction ant colony simulator. Read `GAME_DESIGN.md` and `ARCHITECTURE.md` in full, then inspect `antSim(1).py` as the given minimal example. Do not change the source example. Use Python/Pygame/NumPy.

## Operating rules
1. Treat confirmed V1.3 game rules as requirements. Never silently omit or simplify pheromone navigation, capacity-aware traffic, colony decision-making, cooperative stone movement, digging, or queenless behavior.
2. For unspecified mechanics, choose the smallest configurable and documented prototype default; list all such defaults in README. Where a contradiction exists (stone weight/speed example), preserve explicit examples and flag the formula as unresolved.
3. Keep simulation logic independent of rendering and frame rate. Use deterministic random seeds and automated tests.
4. Work incrementally. At the end of each phase: run tests, provide exact commands, describe implemented mechanics, incomplete requirements, and next steps. Do not claim a feature is implemented merely because a placeholder class exists.
5. Do not rewrite the project into a single large script.

## Phases
### Phase 1: Runnable foundation
Project skeleton, world arrays, four colored colonies and 2x2 queens, two workers each, terrain with capacity 1 on ordinary soil / 4 after digging, food sources, fixed tick and smooth animation, runtime speed controls, pause/end/reset, turn cap, basic stats. Test capacity and timing. Produce runnable build.

### Phase 2: Resource ecology and real autonomy
Scent diffusion with bounded radius, food harvesting/transport to own queen, pheromone data per faction with decay/reinforcement, worker FSM and meaningful return-to-base paths, dynamic digging for traffic, periodic food spawning and downgrade. Test round-trip resource delivery and trail decay.

### Phase 3: Colony economy and warfare
Queen upgrades, workers/soldiers, all eight perks, queen threat detection, adaptive production, combat, queen death trophy, last-queen win, queenless hunger damage and direct food-to-HP recovery, queenless aggression and perk removal. Test edge cases and turn ordering.

### Phase 4: Construction, stone teamwork, and information overlays
Soil stacking/strength, cooperative stone movement with spatial constraints, stone composition, More Information overlays for scent/trails/territory, performance optimization and regression tests at 512x512.

## Acceptance checklist
- Four autonomous factions start at corners; queen occupies 2x2 cells and cannot move or attack.
- Normal soil permits one ant; dug passage permits four; occupancy never exceeds capacity.
- Workers/soldiers obey one nonmovement action per tick and their movement budgets.
- Food smell expands over time and food sources respawn/spawn on schedule with spacing.
- Ants genuinely use pheromones and navigate back to their own queen.
- Production/upgrade/perks follow design; queen makes adaptive production decisions.
- Queen death removes victory eligibility but surviving ants persist; lose 1 HP each five ticks, can eat food to heal 1 HP/unit up to maximum, attack foreign ants, and lose perks.
- Last living queen wins; unresolved turn cap produces no winner.
- UI speed, pause, end, reset, turn limit, and overlay toggles work.
- Full functionality is covered by tests or explicitly flagged as incomplete.

## First Codex task
Implement PHASE 1 ONLY, run available tests, and show me the resulting file tree, run instructions, tested behavior, and any open design decisions. Wait for my approval before starting Phase 2.
