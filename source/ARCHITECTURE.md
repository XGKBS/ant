# Ant Colony Simulation — Technical Architecture

## Technical constraints
Python 3, Pygame, NumPy. The provided `antSim(1).py` is a small reference example for sprite rendering and event loop, NOT a complete architecture. Preserve it as reference; do not mutate the original.

## Recommended layout
```
main.py
config.py
requirements.txt
simulation/{engine,world,terrain}.py
entities/{ant,queen,colony}.py
ai/{state_machine,pathfinding,pheromones,colony_strategy}.py
systems/{food,combat,construction,reproduction}.py
ui/{renderer,controls,overlays}.py
tests/
```
You may adapt structure where simpler while maintaining modular separation.

## Model
Use NumPy arrays for dense terrain/occupancy and pheromone data. Do not create 262,144 Python tile objects. Store entity records separately with unique IDs, faction, kind, position, interpolated display position, HP, FSM state, task, cargo, and movement/action budgets. Each faction owns queen, reserves, upgrade/perk status, threat state, and production counters. Food sources have unique IDs, location, tier, remaining units, smell expansion age, respawn deadline. Stone groups have footprint and weight.

## Simulation step
Fixed deterministic simulation ticks independent from display frames. Process scheduled spawns, pheromone decay/updates, ant observations and intent planning, occupancy/path reservations, movement/action resolution, combat/healing, queen decisions/reproduction, deaths, winner checks, and metrics. Specify and test ordering. At 8x, run eight simulation ticks per wall second with render interpolation; avoid frame-rate dependence. Pause freezes both logical state and animation progress.

## Navigation and group behavior
Support capacity-aware pathfinding, digging as a deliberate action to widen chokepoints, crowding/rerouting, and pheromone-gradient following. Bound search and cache/refresh paths when terrain changes. Make pheromone updates local/sparse where possible. Ants have an explicit FSM with states such as explore, follow-food, gather, return-base, dig, fill, move-stone, investigate, defend, fight, forage-to-heal. Group stone movement must be coordinated and atomic.

## Presentation
Separate camera viewport and world grid; 512x512 cells must not be assumed to fit 1:1 on screen. Support zoom/pan or scalable rendering. Cache terrain surfaces and overlay layers; recompute overlays only when relevant data changes. Controls: 1x/2x/4x/8x, pause/resume, end, reset, optional turn cap, three independent More Information toggles. Avoid coupling UI clicks to ant behavior.

## Verification
Provide deterministic seeds, unit tests for terrain capacity, food regeneration, scent radius, pheromone decay, queen upgrades/perks, fractional economy, turn limits, death/queenless periodic damage, healing cap, and last-queen winner. Integration tests: four factions spawn, food route reaches queen, ants do not overfill cells, pause freezes tick, 8x advances 8 ticks/sec approximately, queenless soldier eats but cannot carry food to queen. Benchmark 64x64, 128x128, and 512x512, report actual hardware/time and ant counts, do not invent performance figures.

## Delivery discipline
Keep code runnable after every phase. Provide README with install/run/test commands and keyboard controls. Keep a requirement-to-implementation checklist; mark incomplete behavior clearly. Never claim full support for placeholder logic. Explicitly disclose default decisions on unresolved rules.
