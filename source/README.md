# Ant Colony Simulation — Supply Depot V2 and Performance-First Autonomy

Python/Pygame/NumPy simulation implementing Phases 1–3, Phase 4A performance optimization, Phase 4B physical soil and cooperative stones, Phase 4C observational overlays, Phase 4D graphical setup and controls, and Phase 4E upkeep, debt/starvation, queen food healing and public fixed supplies. The original `antSim.py` and three design documents remain unchanged. Phase 4E intentionally changes food economics and foraging outcomes.

## Install, run and verify

Portable play: double-click `D:\Codex\ant\ant.exe`; keep `_internal` beside it. No Python installation is required. For source development, create the Python environment described below inside `D:\Codex\ant\source`. PowerShell:

```powershell
cd D:\Codex\ant\source
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe main.py --focus-colony red
.\.venv\Scripts\python.exe main.py --size 64 --seed 7 --max-turns 300
.\.venv\Scripts\python.exe main.py --perks production,exploration,warfare,speed
.\.venv\Scripts\python.exe main.py --perks blitz,greed,heavy-lifting,sensitivity
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --focus-colony red --smoke-frames 10
.\.venv\Scripts\python.exe -m benchmarks.phase3 --turns 20
.\.venv\Scripts\python.exe -m benchmarks.natural_phase3 --size 64 --turns 300
```

`--perks` selects exactly one ability per faction in red, yellow, blue, green order; repeats are permitted. CLI validation rejects unknown or missing choices. Defaults are production, exploration, warfare, speed. No ability is only a label.

On a fresh machine with Python 3.11+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Tested: Python 3.13.5, NumPy 2.5.4, Pygame 2.6.1 / SDL 2.28.4.

## Controls and inspection

| Input | Behavior |
|---|---|
| Space / Esc | Pause/resume all systems and animation; open/close pause menu |
| 1 / 2 / 3 / 4 | Request 1x / 2x / 4x / 8x |
| E / R | End preserving results / restart current configuration |
| T | Edit turn cap; simulation pauses while editing |
| Enter / Esc / Backspace | Apply / cancel / edit; blank means unlimited; zero is rejected |
| Wheel over map / Arrows | Cursor-centered zoom 1–16x / bounded pan |
| Middle or right mouse drag | Grab and pan map; left click remains inspection |
| Wheel over information panel | Scroll statistics and inspection |
| F | Cycle colony focus |
| Home or V | Full-map overview |
| Left click ant | Inspect; repeat to cycle overlapping workers/soldiers |
| Left click empty terrain | Clear selection |
| M / More Information header | Expand or collapse the overlay menu; active layers remain on |
| S / P / C | Independently toggle Food Scent Range / Pheromone Trails / Territory Coverage |
| G / H | Cycle pheromone faction (all, red, yellow, blue, green) / type (all, base, food, battle) |
| Left click overlay row or filter | Same operation as its keyboard shortcut |
| Close window | Quit |

Optional `--focus-colony red|yellow|blue|green` preserves overview access. Restart replays the current map, seed, abilities, runtime cap and selected startup camera; speed and overlay/filter preferences remain. New Game opens configuration for a replacement world. Ended games require Restart or New Game; final statistics remain inspectable until then. An already completed result cannot be overwritten by pressing End again.

## Graphical setup and session controls (Phase 4D)

Run `main.py` without arguments for **New Game / Settings / Quit**. No world or simulation turns exist before Start Game. New Game offers 64, 128, 256 and 512 square maps (default 512), a seed, optional positive turn cap, and independent ability selection for red/yellow/blue/green. Select a faction card, then an ability; duplicates are allowed. The description explains the actual existing mechanic. Click a numeric field to replace it, use Ctrl+A/Backspace, or Tab between fields. Click **Start Game** (or Enter). Blank turn limit means unlimited.

The fixed sidebar toolbar provides Pause/Resume, Menu, End, Restart, New Game, Settings, Overview, Colony focus, Turn cap and four speed buttons. Space or Esc opens the pause menu with Resume, Restart, New Game, Settings and Quit. Settings changes target drawing FPS (30/60/120), information text size (18/20/22), and startup camera for the next game/restart. These preferences do not change logical turns or abilities. The resizable window has a minimum 800×600 client area; menus scale to fit and the information panel scrolls. Selecting an ant scrolls its inspection into view. A map that fits is centered with its normal aspect-ratio letterbox; panning cannot reveal additional blank space beyond that letterbox. Larger zoomed maps clamp to their edges.

CLI compatibility: explicit `--size`, `--seed`, `--max-turns`, `--perks` or `--focus-colony` starts immediately, as in earlier phases. `--play` starts defaults immediately. **`--setup` overrides immediate play**, showing the main menu with CLI configuration prefilled for New Game. GUI edits then override those values for the next world. `--setup` and `--play` are mutually exclusive. `--smoke-frames N` uses dummy SDL drivers and immediate play unless `--setup` is specified.

```powershell
.\.venv\Scripts\python.exe main.py --setup --size 128 --seed 42
.\.venv\Scripts\python.exe main.py --play
.\.venv\Scripts\python.exe -m benchmarks.smoke_phase4d --dummy --output work\phase4d-smoke
.\.venv\Scripts\python.exe -m benchmarks.phase4d --output work\phase4d-ui.jsonl
```

Pause also works while editing a cap: Space cancels the edit and pauses/resumes relative to the pre-editor state. Enter/Apply commits, Esc/Cancel restores the prior cap; Ctrl+A selects the numeric contents. Losing window focus automatically pauses an active game and ends any drag. Normal KEYDOWN shortcuts and Windows TEXTINPUT-only shortcuts are supported without double-processing the normal key/text pair.

### Timing and responsiveness boundary

The application credits elapsed time only when the preceding interval was active, at that interval's speed. Setup, settings, pause and world loading accrue no simulation debt. Pre-pause active-time debt and fractional interpolation progress are retained, so a previously CPU-bound game may still have legitimate queued turns after Resume; the sidebar reports the queue. One complete logical turn runs per rendered frame at most, with no work discarded. Drawing FPS is a target, not a simulation throttle.

The engine and A* remain synchronous on the UI thread. Events arriving after polling can wait for the current full turn; at high populations this can exceed a second. This phase repairs input routing and paused-time accumulation, but does not make a running A* search interruptible. Full overlay refreshes also cost more than cached frames. Proposed future work is deterministic resumable planning with stable turn snapshots, ordered commits and RNG ownership, under a separate approved performance phase. No pathfinding algorithm or simulation rule was changed here.

Workers are enlarged circles; soldiers are larger diamonds, with faction color, dark outline and heading mark. Pale dots indicate food cargo; tan squares indicate soil cargo or ground stockpiles. Reinforced ground is light tan; composed/large stone is dark gray. Living queens are stationary 2×2 squares; a crossed outline marks a dead queen. Food is orange. Selection marks the worker/soldier and its current movement target.

The panel shows worker/soldier counts, reserves, queen HP, upgrade level (L0/L1), selected ability, ability loss, threat, queenless state, deliveries, eating, digging and attacks. Inspection shows type, faction, normal HP cap, cargo/capacity, FSM, logical position, movement target, combat target type/ID, last action, movement budget, soil cargo and construction job ID. Planned FSM/target describe the upcoming interval; logical position/cargo/HP describe completed ticks. Camera/inspection never inform AI. The More Information menu adds independent observational overlays; see the Phase 4C section below.

## Food economy and fixed supplies (Phase 4E)

These rules supersede earlier descriptions of nonnegative reserves or absent queen healing. All unrelated movement, combat, perks, construction, pathfinding and UI controls remain.

### Progressive upkeep and queen survival

Every **100 completed turns**, each colony pays upkeep for its **current living ordinary ants** (workers and soldiers), excluding the queen. Let `q, r = divmod(N, 50)`:

```python
upkeep = 25*q*(q+1) + r*(q+1)
```

This is progressive: 107 ants cost **171**, not 321. Populations 0/50/100/150/200/250/300/1000 cost 0/50/150/300/500/750/1050/10500. The aggregate cost uses integer arithmetic; settlement sorts living ants by ID to assign each ant its progressive marginal cost. Every colony, including queenless survivors, settles independently; dead/pending/non-ant entities are excluded. Births completed on the boundary count.

At each 100-turn settlement, ordinary ants pay from source food on their current tile, then friendly Honeypot storage within 10 cells, then their own cargo, then the signed colony reserve. Honeypots have zero upkeep and are excluded from progressive brackets. Upkeep may create debt, with no zero clamp. Existing deliveries repay it through the same inventory. Reproduction, bonus births and paid upgrades cannot spend a negative reserve. No separate hunger inventory exists.

A living queen at negative end-of-turn reserves takes **1 HP every two consecutive negative-food turns**. The first turn counts one; the second damages; the counter resets at nonnegative food. Recovery cannot retain starvation credit. HP floors at zero and death goes through the existing lifecycle, trophy, perk loss, queenless hunger and victory code. Queenless colonies keep their signed historical reserve and upkeep ledger but have no queen to heal/starve.

A surviving queen automatically restores up to **2 HP per completed turn**, paying exactly **1 food per HP** from available positive reserves. It cannot borrow or exceed the existing queen HP cap (the original queen HP default remains authoritative). Exact half-unit food permits 0.5-food/0.5-HP healing. Dead queens never heal. Metabolism is not an extra worker action or extra queen birth: existing action/birth limits remain.

Deterministic completed-turn order:

1. Commit planned movement and visit/traffic updates.
2. Ordinary food ecology, station refills, pheromone decay.
3. Existing queenless hunger/death cleanup, simultaneous combat and cleanup.
4. Construction and one ant action: eating, digging/material work, pickup, delivery or reporting; reinforce trails.
5. Threat assessment and existing upgrades/reproduction.
6. **Upkeep** on turn 100/200/300/etc, using living population after that turn's births/deaths.
7. **Queen healing** from remaining positive reserves; then **starvation** from actual end-of-turn signed reserves.
8. Existing death cleanup (including starvation trophies), scent rebuild, victory/cap, and next planning.

Thus delivery can avert starvation that turn; purchases precede maintenance and healing; upkeep can prevent healing; combat-killed queens cannot heal. Living queens can heal nonlethal combat damage after combat. Each new settlement/survival operation is guarded against duplicate same-turn processing. Pause/menu/rendering never calls them.

### Twelve public permanent supply stations

Each queen anchor `(x,y)` has three stations, in this exact order (positive Y downward):

| Corner | A | B | C |
|---|---|---|---|
| Top-left / Red | `(x+5,y)` | `(x,y+5)` | `(x+5,y+5)` |
| Top-right / Yellow | `(x-5,y)` | `(x,y+5)` | `(x-5,y+5)` |
| Bottom-left / Blue | `(x,y-5)` | `(x+5,y)` | `(x+5,y-5)` |
| Bottom-right / Green | `(x,y-5)` | `(x-5,y)` | `(x-5,y-5)` |

The diagonal uses five cells on **each** axis. Nests are at `(2,2)`, `(size-4,2)`, `(2,size-4)`, `(size-4,size-4)`. Default five-cell nest clearance permits all exact offsets on 64/128/256/512 maps. Placement changes no terrain or soil and consumes no RNG. If an exact site is blocked/conflicting/outside/unreachable under existing bounded navigation, candidates sort by Manhattan distance to intended site, correct direction, angular deviation and coordinates; the first reachable traversable unused site wins. Every site records intended/actual coordinates and the precise fallback reason. Initialization raises an explicit error if no site is possible.

Stations are separate entities in `world.stations`, not ordinary Micro/Small/Medium/Large nodes. Each starts with **5 food** (60 globally, separately accounted initial allocation), adds **5 every 25 completed turns** (60 globally per refill), and retains uncollected stock without a cap. Identity and position never change, depletion never removes a station, and ordinary respawn/downgrade/Greed tier rules do not apply. Existing ordinary-food spacing/generation remains unchanged; fixed public sites are exempt from ordinary-node spacing and can share a grid cell with an ordinary source. When shared, stable existing ordinary-source-first pickup resolves collection deterministically.

Prototype station scent radius is **4 cardinal traversable cells**, expanding one per turn through the existing field. Empty stock has no scent; refilled empty stock expands from age zero. Stations remain traversable and reserve no ant occupancy. Stone destination validation protects them exactly like existing ordinary food sites; filling/reinforcement remains traversable. No soil is created/removed to place a station. Stations remain active after any queen dies; context faction is never ownership.

All ants have public access to the immutable tuple `world.station_locations`. Workers physically navigate to sites, gather within existing remaining load (including Heavy Lifting and soil cargo), and deliver to their own queen through the original action. Refill never credits colony reserves. Enemy workers may gather; wounded queenless workers/soldiers may eat directly under existing rules.

AI keeps combat, defense, reporting, carried-food return and active construction priorities. Locally observed/remembered ordinary food and actual scent/trails continue to guide foraging. Idle workers lacking those cues may target the nearest public site, with deterministic ID tie breaks and the existing A*/capacity/action machinery. Stock is observed only within existing local sensing; hidden remote quantities do not enter station selection. Locally observed empty stations are avoided until the next scheduled refill; bounded route failures retain the existing cooldown. Debt makes an otherwise idle, empty worker consider supplies before starting new idle construction/material work; it does not cancel an active job or combat. Wounded queenless ants can also use public sites for direct healing. Soldiers' food knowledge does not block soil return/fill work, since soldiers do not perform queen food delivery. Soldiers can carry personal rations within their shared physical load.

### Food Economy UI and accounting

Click **FOOD ECONOMY** immediately below More Information. The independent expandable section displays all four colonies' living population, signed reserve, progressive upkeep, settlement countdown, debt, queen HP/cap, starvation/countdown, last-turn healing and food cost, plus cumulative upkeep/healing expenditures. Scroll the sidebar at small window sizes. Existing diagnostics and inspection remain intact.

Stations use a **white outlined square with a cyan +** (gray + when empty). Click a station to inspect stock, next refill, generated/collected amounts, public context and placement reason. Ant inspection has click priority if markers overlap. The section separately reports food at stations, food carried, total deliveries, initial station allocation, generated refills and latest refill/countdown. Every overlay/camera control remains observational and works with the same world coordinates.

`FoodSystem.accounting()` returns signed inventories, initial allocation, cumulative generated/consumed food and a residual. Inventory includes ordinary nodes/trophies, stations, ant cargo and **signed** colony reserves. Generation includes ordinary respawns/new sites, trophies and station refills. Consumption includes existing reproduction/upgrades, direct eating, recorded death/perk-loss waste, upkeep and queen healing. Transfers cancel. Natural worlds must keep `inventory + consumed - generated - initial == 0`; manually injected benchmark reserves use the initial residual as a closed-interval offset (160 in the population fixture).

Existing `spent_half` still tracks reproduction/upgrades; `upkeep_spent_half` and `healing_spent_half` track new expenses separately. `generated` retains its old ordinary-node-count meaning; `generated_units` adds an exact ordinary-food quantity ledger. `Supply.initial_units` and refill totals distinguish new generation from actual collection/delivery.

`colony_economy_enabled` and `supply_stations_enabled` default **True**. They are Python configuration switches for isolated old-subsystem tests and controlled comparisons; normal GUI/CLI games enable all Phase 4E rules. Five legacy fixture setups explicitly disable only the new unrelated sources/sinks needed for their original closed-food/empty-scent/bespoke-stone assertions. No original assertion was weakened or deleted. Phase 4E tests exercise enabled defaults separately.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m benchmarks.capture_phase4e --output work\phase4e-images
.\.venv\Scripts\python.exe -m benchmarks.phase4e --output work\phase4e-benchmarks.jsonl
```

The benchmark uses the original 512×512/seed-7 distributed 100/500/1000 population fixtures, an uninstrumented 30-turn window, and separately instrumented subsequent turns through 50. It records populations/reserves, complete new checkpoints, signed accounting, soil, subsystem timings, rendering, controlled queued input delay and memory. Inclusive AI timings contain A* and must not be added to it. UI-only repeated replay/pause/restart and overlays must match Phase 4E checkpoints; old outcomes intentionally differ. The synchronous A* limitation remains: public routes can increase search work and do not solve lag. Detailed actual timings and limitations are in the Phase 4E report.

## Economy and abilities

Food uses exact half-unit transactions. Reserve charges convert to integer half-units before arithmetic. `spent_half`, `upgrade_spent_half` and `received_half` provide per-colony ledgers; cargo and source amounts remain exactly representable multiples of 0.5. Ordinary workers/soldiers cost 2 food. A queen spends 10 food to upgrade automatically when affordable; a paid upgrade consumes her turn. Only upgraded queens can produce soldiers. Spawn capacity is checked before charging for a birth; newborns begin moving/acting on the next interval. Each queen creates at most one ant in a turn, including free bonus births.

To fund actual upgrades, non-Production queens stop buying workers and save for the 10-food upgrade once they have eight living workers, or at contact-or-higher threat with at least two workers. The panel shows `L0 save`. Production queens can continue toward their ten-worker free upgrade. This configurable savings threshold is a prototype strategy choice, not a change to costs.

| Ability | Implemented effect |
|---|---|
| Production | Ten produced workers, excluding starting workers, automatically upgrade the queen without a charge. After upgrade, every ten births of the same type queue one free ant of that type. Free births take a later turn and count toward later ten-ant milestones; they never bypass the one-birth limit. |
| Exploration | Worker cost 1.5 food. |
| Warfare | Soldier cost 1.5 food. |
| Speed | Worker movement 3 instead of 2. |
| Blitz | Soldier movement 4 instead of 3. |
| Greed | Gathering from five distinct source IDs of the same tier earns one token that prevents the next respawn of that tier from downgrading. |
| Heavy Lifting | Load 1.5; workers actually harvest and transport up to 1.5 food per pickup. Soldier load is also 1.5, but soldiers still cannot transport ordinary food. |
| Sensitivity | Worker sensing 3 instead of 2; queen alarm sensing 15 instead of 10. |

Greed counts each source once within a five-source batch, regardless of pickup quantity. A completed batch clears its ID set; later batches may reuse IDs. Tokens stack by tier and apply to the next world respawn of that original tier. Competing eligible tokens resolve by faction order, then source-list order. Trophy sources are excluded. Queen death clears unused tokens and queued bonus ants. These counting/queue choices resolve previously unspecified semantics and the bonus/one-birth conflict without bypassing the birth limit.

## Queen threat and autonomous behavior

Queen strategy uses actual nearby enemies, foreign pheromone presence, worker reports and recent attacks. Foreign signals alone cause alert; sensed enemies cause contact; enemies within five cells cause near-base; direct interaction range, queen HP ≤15 with enemies present, or a recent queen attack cause critical. Recent attacks/reports persist for three turns. Safe is restored when the evidence expires. A spatial index bounds local enemy queries.

Default worker/soldier production ratios are safe 100/0, alert 75/25, contact 50/50, near-base 25/75, critical 0/100. An integer accumulator realizes these ratios deterministically over paid births and survives threat changes. Unupgraded queens always produce workers. Serious threats broadcast defense targets to colony members; workers and soldiers move to intercept. Quiet outer approaches can now be reinforced using physical excavated soil; combat and threat priorities remain unchanged.

The FSM includes explore, seek-food, gather, return-base, dig, return-report, patrol, investigate, defend, fight and forage-to-heal. Workers explore least-visited local cells, follow rising scent or their faction's food trail, and remember only observed sources. Soldiers patrol/explore, follow own battle trails, investigate foreign presence and engage sensed enemies. Workers carry unknown signal reports home; a report is a nonmovement action, or accompanies a food delivery. Foreign trail values never guide navigation as if they belonged to the colony.

Known static terrain and own queen location are available to bounded A*. Hidden food locations are not. Routes cache until the goal/terrain revision changes or becomes invalid. Full cells incur cost; blocked steps try alternate routes, wait, or dig. The search limit is 4,096 expanded nodes, with deeper-node tie breaking. A failed food target is suppressed for 25 planning turns. Local trail revisit penalties release stale gradients. Routes/exploration remain heuristic and may detour or fail in adversarial mazes.

## Combat, death and survival

Workers: 5 HP, damage 1, movement 2, sensing 2. Soldiers: 12 HP, damage 3, movement 3, sensing 3. Queens: 50 HP, damage 0, movement 0. Perks modify only the listed derived attributes while the queen lives.

Default combat range is cardinal distance ≤1, including enemy ants sharing a capacity-four cell. Targets are nearest eligible enemies, then ants before queens on a distance tie, then stable entity ID. Target distance to a queen uses her whole 2×2 footprint. All ants alive at the action snapshot choose one attack; damage is aggregated and applied simultaneously, so mutual kills land. Queens never enter the attacker loop. There is no collision damage. Combat takes action priority over healing, digging, reporting and food handling.

Dead ants are removed before healing, their occupancy is released and their cargo is recorded as discarded. They leave no loot and cannot revive. Queen death is recorded once, permanently removes victory eligibility and reproduction, and immediately disables every perk. Derived movement/load/sensing/costs consult the live-queen state, avoiding stale buffs. Historical trail/memory remains usable and decays normally; base trails stop being reinforced without a queen.

Dead queen footprints become ordinary traversable soil. Default trophies contain 50 units with scent radius 24 and do not respawn. A trophy normally appears at the queen anchor. If another source is closer than five cells, its site is converted to trophy and receives the added units, preserving source spacing and existing food quantity. Its earlier respawn is cancelled. This merge/location behavior and trophy values are prototype defaults.

Queenless ants remain active. Every five turns after their queen's death (death+5, death+10, …), each loses 1 HP before actions. An ant reaching zero is removed before it can eat. Survivors attack detected enemies first. Damaged survivors seek remembered/local food, consume up to one food per action and heal the same amount, capped at normal HP; soldiers can eat directly but never transport it. A worker may eat existing cargo first. Healthy queenless ants continue exploring and engaging enemies without collecting food for a dead queen. Remaining reserves are stranded historical stock.

On Heavy Lifting loss, cargo above the restored load of 1 is discarded and recorded (at most 0.5 per ant), rather than leaving an illegal load or inventing ordinary-ant loot. This is an explicit prototype normalization rule. There is no free healing during perk removal.

The last living queen wins, regardless of surviving queenless ants. If all queens die in the same tick, no faction wins. Victory is evaluated after the complete simultaneous action/death step and takes precedence over a cap reached that tick. A cap/manual end with multiple living queens reports no winner and freezes statistics.

## Resource ecology and terrain retained from Phase 2

The default world is 512×512 NumPy terrain/capacity/occupancy arrays. Four queens start with two workers each, two-cell edge margins and a five-cell nest clearance. Seed 7 is deterministic. Ordinary soil capacity is 1; dug passages hold 4; stones and living queen footprints hold zero. Single-stone density is 0.025 and 2×2 stone-anchor density 0.002. Static patches may merge or be trimmed by nest clearance; ordinary cells are individual movable groups, while cardinally connected large-stone cells form rigid footprints. Existing patch merging and nest trimming are preserved.

Twenty-four initial food sites cycle micro/small/medium/large: units 1/5/10/25 and scent radii 2/4/8/16. Scent expands one traversable cardinal cell per turn. Intensity is `(maximum_radius+1-geodesic_distance)/(maximum_radius+1)`; overlapping fields take the maximum. Exhaustion removes scent; respawn starts at age zero. Workers pick up on the source cell and deliver on a cardinal queen-perimeter cell. Soldiers cannot do ordinary food transport.

Exhausted sources respawn 25 turns later, one tier lower. Micro renews as micro by default; `micro_respawn_tier=None` leaves it exhausted. Every 50/75/100 turns add four small/two medium/one central large sources, executing all coincident schedules. Spacing is at least five Euclidean cells, including exhausted reserved sites. Sources must be flood-fill accessible; dead queen cells are added when released. Large spawns use a central disk of radius `max(8, floor(size/6))`. Impossible placements queue and retry on generation events and every 25 turns; crowded maps may never fit every queued spawn.

Faction-specific base/food/battle NumPy fields use sparse active-cell decay: multiplier 0.96, cutoff 0.01. Deposits are `min(20, max(existing,strength)+0.25)`. Base strength is `8/(1+0.1*distance_to_queen)`; food strength is `8/(1+0.1*return_path_sample_count)`; battle attacks deposit strength 8. Deposits include stationary path samples. Persistent food/base facts come from entities, not decayed trail values.

Two blocked turns or eight actual arrivals can trigger adjacent soil widening. Digging uses the one action and ends remaining movement that interval. Each excavation now produces one physical soil unit, carried if load permits and otherwise left at the excavated cell. Physical deposit, filling and stacking are implemented below.

## Fixed tick and action ordering

One turn is one second at 1x. Ants receive their actual kind/perk movement budget and cardinal substeps; each path interpolates smoothly over the interval. Planning rotates priority and reserves occupancy immediately. Occupancy describes endpoints, not visually enlarged circles or continuous physical collisions.

1. Commit movement, visit/traffic counters and the completed turn number.
2. Age/respawn/generate food and decay pheromones.
3. Reset action budgets; apply due queenless hunger; remove dead ants/transition already dead queens.
4. Resolve simultaneous attacks; remove deaths, create trophies and disable queen perks.
5. Coordinated crews spend their one action on valid work after combat. Other survivors use at most one action: direct eating, digging, material handling, delivery/report or pickup. Wounded queenless ants and combatants are excluded from crews. Food actions retain stable ant-list order.
6. Reinforce local trails, assess threats, upgrade/reproduce, then Phase 4E upkeep, queen healing/starvation, death cleanup and scent rebuild.
7. Evaluate last-queen/all-dead victory, then turn cap; otherwise observe and plan the next movement.

New births cannot act in their birth tick. The UI processes at most one completed tick per frame and retains the rest in the accumulator; no logical time is discarded. `backlog` shows pending turns when CPU capacity falls behind requested speed. Pause freezes that backlog too. Headless `Engine.advance` defaults to draining all due ticks for deterministic tests. Large populations do not currently sustain 8x; one individual expensive tick can still delay control handling.

## Configuration, verification and incomplete work

Phase 4A changes only performance internals. A* uses live zero-copy byte views of capacity/occupancy, reusable integer cost/parent arrays, generation stamps and integer-encoded heap ties. It preserves Phase 3's exact neighbor order, movement costs, tie breaking, expansion limit and global route-recalculation policy. Geometry/distance-map caches and guarded full-result memoization were tried but not retained: gains were inconsistent or absent and memory/validation overhead was unnecessary. No AI observation is skipped, and no combat or reproduction limit is introduced.

Scent footprints now depend on local traversability revisions. Soil→passage keeps both cells traversable, so it does not rebuild a connectivity-only scent footprint. Opening/blocking cells inside a source's radius invalidates that source; remote changes do not. Global terrain revisions remain intact for routes and rendering. Runtime terrain changes must use the existing `Terrain.set`/`dig` API, as before.

The A* workspace costs approximately 4 MiB on a 512×512 map and is allocated lazily. Local topology versions add 2 MiB. These dense arrays avoid per-tile Python records. Shape changes and generation wrap are handled. No new dependency is required.

The frozen Phase 3 baseline is retained under `D:\Codex\2026-10-20\read-game-design-md-architecture-md\work\phase3_baseline`. Performance reports use fresh, matched 512×512/seed-7 distributed/contact fixtures at 100, 500 and 1,000 starting ants, with 20 turns and the same timed window as Phase 3. Untimed SHA-256 checkpoints compare RNG, entity state, actual paths, food/economy/combat counters, terrain, occupancy and dense pheromones; only internal route-revision metadata is omitted. Final comparison rejects behavior/population differences.

```powershell
# From D:\Codex; use another output path to retain the delivered measurements.
.\.venv\Scripts\python.exe -m benchmarks.phase4a --output work\phase4a-repeat.jsonl
.\.venv\Scripts\python.exe -m benchmarks.phase4a --profile --counts 500 --scenarios distributed --output work\phase4a-profile.jsonl
.\.venv\Scripts\python.exe -m benchmarks.compare_phase4a --before BEFORE.jsonl --after AFTER.jsonl --output comparison.json
```

Profiling showed A* dominated the original 500-ant run (40.3 of 44.0 profiled seconds). The final benchmark report records average/worst timings, identical per-turn population histories, and all before/after fingerprints. Large populations remain limited by search work; 1,000 distributed ants still do not sustain real-time 1x. Single expensive ticks can delay controls. Profiles include instrumentation overhead; the benchmark table uses unprofiled timings.

`config.py` exposes the defaults above plus perk selection, integer upgrade cost, five threat ratios, queen alarm/near-base/critical thresholds, attack-memory turns, hunger period and trophy units/scent. `reproduction_enabled` and `combat_enabled` default true; tests disable them explicitly to isolate earlier resource-only assertions. Normal CLI games always run the complete Phase 3 rules.

Tests cover earlier capacities/timing/resource ecology and new economy conservation, fractional costs, all eight perks, free-birth limits, blocked spawning, adaptive ratios, combat/no loot, queen death/trophies, hunger, eating/caps, no resurrection, perk removal, reporting/battle trails, deterministic integration, victory and manual-result preservation. Benchmark fixtures inject 100/500/1,000 ants on 512×512 maps and report starting/ending populations, births/deaths, attacks and actual timings. `natural_phase3` uses ordinary initialization without injected reserves or ants. Phase 3 delivery outputs contain measurements and screenshots, including an explicitly staged combat/queenless inspection scene.

| Requirement | State |
|---|---|
| Phase 1 foundations, controls and interpolation | Preserved and regression tested |
| Phase 2 resources, faction trails, real FSM, traffic digging | Preserved and regression tested |
| Phase 3 economy, upgrades and at most one birth/queen/turn | Implemented |
| All eight selected abilities affect mechanics | Implemented |
| Threat assessment, ratios and defensive behavior | Implemented |
| Combat, deaths, trophies and occupancy cleanup | Implemented |
| Queenless hunger/eating/aggression/perk loss/no revival | Implemented |
| Last-queen victory, simultaneous deaths and result preservation | Implemented |
| Population/queen/threat/ability/combat inspection UI | Implemented |
| Phase 4A measured performance optimization and behavior checks | Implemented |
| Phase 4B soil conservation, fill/strength/deposit, cooperative stones/composition | Implemented; prototype rules below |
| Phase 4C scent/trail/influence overlays, menu/filter/legend and final integration | Implemented; observational only |

Unresolved final-game decisions remain the prototype defaults above: combat targeting/order/range, threat thresholds and ratios, Greed counting, trophy amount/site/respawn, queenless hunger anchor/eating priority/trail retention, bonus scheduling and excess-cargo loss. They are implemented concrete rules for this prototype, not claims that the design has finalized those choices.

## Phase 4B physical construction — explicit prototype rules

`systems/construction.py` owns game actions and bounded job coordination; `systems/stones.py` owns geometry transactions and the speed curve. These systems import no Pygame. Existing reusable A* workspaces, live occupancy views and localized scent invalidation remain intact. Runtime geometry edits still update route/render revisions and local topology stamps. No sensing, combat or reproduction frequency is reduced.

### Soil inventory and reinforcement

Every initialized map cell has one unit of substrate, including substrate protected underneath a stone or queen footprint. A queen's death exposes that existing substrate; it does not create soil. Excavating ordinary soil transfers its one substrate unit into cargo if the digger has one whole unit of free load, otherwise into a sparse ground stockpile at the excavated cell. The excavation action includes loading the extracted unit when possible. Both workers and soldiers can do this. Stockpiles do not occupy ant slots. Soil uses whole units; food retains its exact half-unit accounting. Combined food plus soil cargo must fit the ant's current load.

The audit invariant is:

`sum(terrain.layers) + loose ground stores + carried soil + job deposits + stone-bound soil = initial soil`

For a default map this is 262,144 units. `excavated_units` remains a cumulative work statistic, never an additional material store. `Construction.soil_total()` audits the actual inventory; whole-map audits run in tests/benchmarks outside their timed window, not on every live action. Geometry-only `Terrain.set` and `Stones.register` are initialization/fixture primitives; gameplay transfers use dig/fill and coordinated jobs. Painting fixture terrain is not a physical construction action.

Digging creates a capacity-four passage with zero substrate layers. Filling transfers one carried unit (or, for the terrain-level transaction, a ground unit at that cell) into terrain. Filled terrain is reinforced immediately. Layer counts 1/2/3 have strengths 1/4/9; no fourth layer is accepted. Adding to ordinary one-layer ground creates two-layer reinforced ground. Every reinforced cell is permanently immune to excavation, including a one-layer filled passage. It remains traversable with capacity one, regardless of strength. Strength describes the stack and excavation immunity; it does not change combat damage, movement cost or HP. Filling is rejected without consuming soil if more than one ant occupies the destination. Access is the same cell or one cardinal neighbor; queens, stones and food sites cannot be filled.

Pick up soil, store soil, fill, and dig each consume one nonmovement action. Carrying a unit home does not create another action. A dead ant drops its soil locally; it creates no food loot. On Heavy Lifting loss, excess food follows the existing Phase 3 recorded-waste rule. If the remaining combined food/soil load is illegal, the whole soil unit is dropped locally and conserved. Bound soil stays in its stone structure when that structure moves. Aborted jobs refund staged soil to their worksite. There is no gameplay soil sink.

### Rigid stones and work speed

Stones never break or disappear. Ordinary initial stone cells form individual groups of weight 4. Connected large-stone patches form rigid groups with weight 4 per cell (a 2×2 group weighs 16). This preserves the original generated terrain exactly, including patches merged together or trimmed by nest clearance. Group IDs have their own namespace, preserving the ant/food ID allocator. Groups may have irregular footprints. Translation is cardinal by one cell per job; rotation is not supported.

Every entering footprint cell must be in bounds, ordinary soil or a passage, empty of ants/queens/other stones, free of loose material, not reinforced, not a reserved food site (even exhausted), and not an active construction worksite. Overlap with the same group's previous footprint is allowed. All cells are validated before any mutation. A failed move changes no geometry, occupancy, material, revision or group position. Vacated cells expose their original substrate: ordinary soil if a layer remains, otherwise a capacity-four passage. Stones never consume or displace that substrate.

Available cooperative load is the sum of current live allied helpers' capacity minus their cargo. Heavy Lifting is consulted at the action snapshot; queenless ants receive no bonus. Only eligible helpers within cardinal distance two of the current footprint and outside the destination count. This two-cell work band represents a small coordinated pushing/pulling team. Helpers stand in legal cells and do not receive an extra displacement, so their own planned movement budget is unchanged. Attacking, dead or wounded queenless ants cannot contribute. Every contributing helper spends its one action for each work tick, including fractional-progress ticks. If an attack, death, blocked destination or lost perk makes the crew insufficient, work pauses rather than moving illegally.

With `r = available_load / weight`, default normalized speed is:

| Load ratio | Normalized work speed |
|---|---|
| r < 0.5 | 0; cannot move |
| 0.5 ≤ r < 1 | 0.25 + 0.75 × (r − 0.5) / 0.5 |
| r ≥ 1 | 1 |

Normal stone handling is one cardinal cell per work turn (`stone_base_speed=1`), independent of ordinary free-walking speed. Consequently four load-one ants move a weight-eight group after four uninterrupted work turns; eight do so in one turn. Recruitment, approaching the stone, combat interruptions and blocked destinations add elapsed time. Exact rational progress avoids rounding drift. Jobs move one cell and finish; excess work never teleports the stone further. `stone_base_speed` supports slower positive values up to one; load/speed breakpoints, ordinary weight, large weight per cell, and work radius are configurable. This is an explicit prototype interpretation of “normal” stone speed, not a linear capacity/weight substitution.

### Five-soil composition

The configurable prototype uses a **shared cardinal seam** between two distinct stone groups (`composition_max_gap=0`, the only supported gap rule), not a new bridge cell. Their disjoint footprints must touch along an edge, and their union must contain at most 16 cells. The traversable deposit site must be within two cardinal cells of each group. Eligible workers or soldiers bring whole soil units to that site, spending one deposit action per unit. Only the fifth unit finalizes the composition; fewer units remain refundable job material. The resulting footprint is exactly the existing union, so no ant, queen, stone or food cell is newly covered. The new group retains one ID, all old bound soil, and the five new bound units; the second registry entry becomes part of the surviving structure. No rock mass is deleted.

Weight is the sum of the component rock weights. Binder soil is conserved separately and does not increase the abstract stone-handling weight. Thus two adjacent ordinary weight-four stones become a two-cell weight-eight structure, retaining all five binder units and reproducing the design's example. This abstract load/binder distinction is an explicit prototype assumption. Binding amount, union size, required shared-edge count (default one), deposit access radius (default two), and component weights are configurable; arbitrary gaps, rotations and unbinding are not implemented. Ordinary adjacent stones can remain separate until ants actually bind them. Worksites and component stones are exclusively claimed across factions, preventing competing jobs from moving the same object twice in a turn.

### Autonomous work and bounded effort

The FSM adds collect-soil, return-soil, store-soil, fill, move-stone and compose-stone. Blocked real routes and repeated target congestion can request local stone relocation. Idle soil carriers near home identify suitable nearby seams only when at least five units are locally available. Otherwise they reinforce quiet outer approaches using their cargo, or store it at the queen perimeter. Idle ants collect nearby ground soil only when a useful local fill exists; fully reinforced surroundings do not cause a pickup/drop loop. A food-seeking worker with soil unloads it locally before pursuing food. Crew recruitment never diverts a worker with known food, food cargo, an enemy target, an urgent defense/report, or healing needs.

The original stone/composition coordinator has one job per faction at a time, a nearby recruitment radius of six, and a workforce budget of at most half the living faction population, retaining at least one worker outside the crew. This is a construction staffing strategy, not a population or reproduction limit. An insufficient prospective stone crew remains unassigned so ants continue normal work. Helpers receive distinct capacity-aware work slots, approach through the existing A*, and work only after arriving. Stone/composition jobs expire after 30 turns and impose a five-turn retry cooldown; unfinished soil deposits are refunded. V2 depots instead preserve paid progress and never refund food. These choices, including the retry cooldown, are configurable except the single-job queue, which is an explicit minimal prototype scheduler rule. They bound repeated searches and prevent construction monopolizing survival. Wide exploration/global engineering, optimal path redesign, persistent multi-cell relocation plans and guaranteed construction completion under hostile traffic are not claimed.

Local stone lookup uses the dense group-ID grid within a bounded radius; nearby helpers use a spatial bucket index. Sparse ground stores hold only actual loose material. No per-action full-map construction scan occurs. Food generation retains the earlier initially reachable candidate pool, checks current traversability, and protects every reserved source from stones. Newly exposed initial rock cells are not added to that pool in this phase. Dynamic stones may require later relocation to reopen a route; reinforced ground remains traversable.

```powershell
cd D:\Codex\ant\source
.\.venv\Scripts\python.exe -m benchmarks.phase4b --output work\phase4b-repeat.jsonl
.\.venv\Scripts\python.exe -m benchmarks.capture_phase4b --output-dir work\phase4b-demo
```

The capture command runs explicitly staged 32×32 scenes through ordinary autonomous planning and action resolution and saves before/during/after images for soil, ordinary and large blocked-route stone moves, and five-soil composition. They demonstrate mechanics, not natural default-world construction frequency. The benchmark uses the unchanged 512×512/seed-7 Phase 3/4A population fixtures and 20-turn timing methodology, adds untimed full material audits and construction-state fingerprints, and reports actual births, deaths, attacks and completed work. Performance remains dominated by bounded A* searches; changed legal terrain/work decisions can change trajectories and combat casualties. Cross-phase timings therefore are workload comparisons, not proof of a same-behavior speedup. See the delivered Phase 4B report for actual measurements.

## Phase 4C More Information visualizations

The right panel contains a More Information menu with three independent checkboxes. Any of the eight on/off combinations is supported. Click the rows, or press **S** for Food Scent Range, **P** for Pheromone Trails, and **C** for Territory Coverage. **M** collapses/expands the menu without disabling active overlays. **G** cycles the trail faction filter through all/red/yellow/blue/green; **H** cycles all/base/food/battle channels. Filters affect only pheromone rendering, never the territory calculation or any ant decision. All earlier keyboard/camera/inspection controls remain. Turn-cap editing keeps its existing input priority. Overlay choices and filters survive reset; the camera returns to its configured startup view, and cached world data and selected-ant state are cleared.

Overlay code lives entirely in `ui/overlays.py`. No simulation, AI, economy, combat, construction, reproduction or pathfinding source file changed during Phase 4C. The renderer never calls a simulation update, rebuilds AI fields, advances the RNG, or writes world arrays. Disabling visualization cannot change game outcomes. Ended/paused worlds can still be inspected and filtered; final statistics remain frozen.

### Actual scent and pheromone fields

Food scent is read directly from `engine.food.scent`, the exact cardinal, obstacle-aware intensity field sampled by ants. The UI does not replace it with circles or its own diffusion algorithm. It displays completed-turn snapshots of expansion, exhaustion, downgraded respawns and generated sources. Multiple sources retain the model's maximum-overlap intensity. Cyan alpha is zero at no scent and `30 + 170*v` for positive normalized intensity `v`; the nonzero floor makes distant low scent visible. Orange source markers are entities, not radius indicators.

Pheromones are read directly from `engine.pheromones.values[faction, channel, y, x]`. Faction colors remain red/yellow/blue/green. At scales below four screen pixels/cell, the overview uses a strength-weighted faction color mix over the selected channels, with alpha `220*sqrt(max_selected_strength/20)` (clipped to the model's 0–20 range). Mixed cells can blend colors; use G to isolate a faction or H to isolate a channel. At close zoom, each logical cell is a **four-column by three-row glyph**: columns red/yellow/blue/green, rows base/food/battle (`B/F/!`). Each subcell uses its own actual strength and opacity; filters blank other contributions. This preserves all channels at close scale without declaring one channel the winner. In the overview, channel filtering is the reliable way to examine a particular signal type.

Reinforcement and decay appear at the next completed-turn snapshot. The UI never adds/removes chemicals. Historical chemicals on a newly stone-covered cell remain visible if the model still stores them there; they decay according to the existing rules. Scent and influence correctly respect their own rules after terrain changes. All overlay layers are drawn above terrain and below food, queens and enlarged ants; overlays do not change hit testing. Stone cells retain their base terrain color when scent/influence is absent; stored historical pheromones may tint them.

### Deterministic influence, not permanent ownership

Territory Coverage is an observational estimate, never ownership, a victory rule, pathfinding input or new resource. Let `K_r(d)=max(0,1-d/(r+1))`, with cardinal/Manhattan distance. For faction f at traversable cell p:

```text
I_f(p) = sum(living ants a of f: weight(a) * K_6(distance(p,a)))
       + living_queen(f) * Q_f * K_12(distance(p,nearest queen-footprint cell))
       + 0.1 * (base_f(p) + food_f(p) + 2*battle_f(p))

weight(worker)=1; weight(soldier)=2
Q_f = 4 + min(2, received_half/20)
        + min(2, (produced_workers+produced_soldiers)/10)
```

The activity term is explicitly cumulative food receipts and births, capped only for display amplitude. Influence uses completed logical ant positions, not occupancy reservations or animated interpolation. Proximity contributions use Manhattan geometry, not a new flood fill or claim of path reachability. Blocked cells, including living queen footprints, have zero influence; queen entities are drawn above them.

If the largest score is below **0.25**, the cell is neutral and transparent. If the second score is at least 0.25 and at least **85%** of the largest, the cell is contested and uses a gray checker pattern. Otherwise the leading faction colors the cell, with opacity increasing with its score. Exact ties above the neutral threshold are contested. A queen's death removes her entire queen/activity contribution. Living queenless ants and retained actual trails still contribute; no movement, carrying or sensing perk enters the influence formula. Faction filtering never hides a competitor from this comparison.

These are explicit visualization prototype defaults. `ui.overlays.InfluenceStyle` is an immutable presentation configuration exposing radii, ant/queen/chemical weights and neutral/contest thresholds; replacing the style invalidates its cache. It does not modify `Config` or game rules. Influence does not persist independently, never grants abilities, and can fade/change as ants move or chemicals decay.

### Cache, viewport and memory policy

Only enabled layers are computed. Full field rasters rebuild at most once per world/turn/terrain revision, plus relevant filter/style changes. Repeated rendered frames reuse them. New world identity on reset invalidates every old cache. Food and territory use one pixel per logical cell. Overview pheromones use one pixel per cell; close-up glyphs are generated **only for the visible logical rectangle**, not a 2048×1536 full-map detail image. Pans/zoom changes replace one viewport cache per layer; they do not accumulate surfaces for every camera position. Pixel conversion to the native display alpha format happens when building a surface, avoiding per-frame channel conversion. Scaling crops before enlarging and never allocates a zoom-sized whole-world surface.

Territory uses four float32 score planes and an int8 label plane, local ant/queen kernels and vectorized actual-pheromone accumulation. It is computed in the UI after completed ticks, outside the simulation decision path. Ant kernels cost bounded local work per ant. Exact scent/pheromone accuracy, ant population, combat and reproduction are never throttled for FPS. Refreshing all 512×512 fields still costs more than a cached frame and may produce a short visual hitch. Since logic and rendering share a thread, actual wall-clock FPS also suffers during expensive simulation ticks; elapsed time remains in the existing accumulator and no logical turns are dropped.

Timing and cache-memory figures are in the delivered Phase 4C report. Benchmarks use SDL's dummy software display, so they measure CPU drawing/conversion and exclude compositor/GPU/vsync costs. They distinguish cached frames, forced full rebuilds and actual simulation time. Python/NumPy memory tracing excludes SDL allocations; explicit cache-byte accounting includes surfaces. Those overlapping figures must not be added together.

### Reproduce verification and captures

```powershell
cd D:\Codex\ant\source
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m benchmarks.capture_phase4c --output-dir work\phase4c-images
.\.venv\Scripts\python.exe -m benchmarks.phase4c --part render --output work\phase4c-render.jsonl
.\.venv\Scripts\python.exe -m benchmarks.phase4c --part simulation --output work\phase4c-simulation.jsonl
# Smaller architectural benchmarks:
.\.venv\Scripts\python.exe -m benchmarks.phase4c --size 64 --counts 100 --output work\phase4c-64.jsonl
.\.venv\Scripts\python.exe -m benchmarks.phase4c --size 128 --counts 100 --output work\phase4c-128.jsonl
```

The staged 64×64 capture scene demonstrates obstacle-shaped scent, all four trail factions and three channels, queenless influence, neutral and contested areas, selected-ant inspection and each overlay separately/all together. It uses real field data seeded through the existing pheromone API and is explicitly not a naturally evolved battle. Separate 512×512 overview/focus captures use ordinary eight-ant initialization and eight actual turns. Test coverage includes all prior phases, all toggle combinations, actual fields, filters, terrain edits, queenless influence, camera alignment, cached-frame behavior, reset/pause/end, read-only arrays, bounded memory, and complete simulation fingerprints with visualization on/off. Paired 100/500/1,000-ant replay benchmarks verify every turn, report births/deaths/populations, and time rendering separately from logical work.

All requested phases are implemented under the documented prototype assumptions. Remaining limitations are heuristic construction/navigation, no rotations/gap bridges/unbinding, approximate influence rather than ownership/reachability, overview color mixing resolved by filters, completed-turn overlay refresh rather than substep interpolation, refresh spikes, and CPU-heavy large-population A*. Further features or rule changes require approval.

## Project tree

```text
D:\Codex\ant\source\
  .gitignore
  ARCHITECTURE.md
  CODEX_INSTRUCTIONS.md
  GAME_DESIGN.md
  README.md
  ai/__init__.py
  ai/behavior.py
  ai/colony_strategy.py
  ai/exploration.py
  ai/navigation.py
  ai/pathfinding.py
  ai/pheromones.py
  ai/state_machine.py
  antSim.py
  benchmarks/__init__.py
  benchmarks/autonomy.py
  benchmarks/autonomy_replay.py
  benchmarks/capture_honeypots.py
  benchmarks/capture_phase3.py
  benchmarks/capture_phase4b.py
  benchmarks/capture_phase4c.py
  benchmarks/capture_phase4e.py
  benchmarks/capture_strategy_depots.py
  benchmarks/compare_phase4a.py
  benchmarks/compare_render_phase4e.py
  benchmarks/depot_v2.py
  benchmarks/honeypots.py
  benchmarks/natural_phase3.py
  benchmarks/phase2.py
  benchmarks/phase3.py
  benchmarks/phase4a.py
  benchmarks/phase4b.py
  benchmarks/phase4c.py
  benchmarks/phase4d.py
  benchmarks/phase4e.py
  benchmarks/smoke_phase4d.py
  benchmarks/strategy_depots.py
  benchmarks/validate_depot_v2.py
  config.py
  entities/__init__.py
  entities/models.py
  main.py
  requirements.txt
  simulation/__init__.py
  simulation/engine.py
  simulation/spatial.py
  simulation/terrain.py
  simulation/world.py
  systems/__init__.py
  systems/combat.py
  systems/construction.py
  systems/depots.py
  systems/economy.py
  systems/food.py
  systems/honeypots.py
  systems/information.py
  systems/lifecycle.py
  systems/perks.py
  systems/reproduction.py
  systems/stones.py
  systems/strategy.py
  systems/supply.py
  tests/reference_pathfinding.py
  tests/test_application.py
  tests/test_colony_systems.py
  tests/test_construction.py
  tests/test_controls.py
  tests/test_depot_v2.py
  tests/test_food_economy.py
  tests/test_foundation.py
  tests/test_honeypots.py
  tests/test_information_behavior.py
  tests/test_overlays.py
  tests/test_performance.py
  tests/test_personal_upkeep.py
  tests/test_resources.py
  tests/test_strategy_depots.py
  ui/__init__.py
  ui/application.py
  ui/camera.py
  ui/controls.py
  ui/food_economy.py
  ui/overlays.py
  ui/renderer.py
  ui/widgets.py
```

Current incremental integration adds strategic reserves, communicated Total War, Honeypots and globally linked cooperative supply depots on top of the existing Phase 4F navigation work. No additional phase is started.


### Personal food upkeep update

Upkeep occurs every 100 completed turns. Within each faction, ascending living ant ID assigns costs: first 50 ants pay 1 each, next 50 pay 2 each, and so on. This preserves the existing aggregate formula. Queens and dead ants are excluded. The later direct-source/Honeypot priority below supersedes the original personal-first order: current-tile food, friendly Honeypot, own cargo, then the shared signed reserve including debt. Total upkeep includes both payment sources, with separate half-unit personal/shared ledgers. Personal upkeep is not also counted as direct healing consumption.

Workers and soldiers normally carry at most 1 food; Heavy Lifting retains its existing capacity effect. Food and soil share physical capacity. Soldiers opportunistically collect rations at their current cell using one nonmovement action, retain patrol/combat priorities, never deliver to queens and never lay worker food-return trails. Workers retain collection/delivery behavior; food still carried at settlement can pay personal upkeep. Earlier deliveries and reproduction in that turn retain existing ordering. No additional ration inventory or reserved food exists.

Signed debt and starvation penalties are unchanged: a living queen loses 1 HP every two consecutive negative-reserve turns. Queen healing, queenless direct eating and five-turn HP loss, perk removal, station refills every 25 turns and ordinary food schedules remain unchanged.


## Strategic reserve and Total War

These incremental rules are enabled by default. They preserve 100-turn upkeep, signed reserves/debt, starvation damage, queen healing, perks, combat, movement/action limits and the current Phase 4F shared navigation system. They intentionally change production allocation and task choices. They do not complete the separately pending Phase 4F responsive-execution work.

### Queen strategy and communication

Each living queen targets `max(strategic_reserve_min, ceil(strategic_reserve_per_ant * living_workers_and_soldiers))`, default `max(10, ceil(0.5*N))`. This is a policy within the existing signed queen balance, never a second inventory; V2 depot receipts credit this same balance. Recalculate on population changes; births check the target after the prospective birth. Peace and Alert paid births and paid upgrades retain this reserve. Free Production-perk births keep their existing rules and cannot occur from a negative balance. Upkeep and healing ignore this allocation floor and retain their existing penalties/costs. A queenless faction has target zero.

Peace uses existing economic production ratios. Any non-safe assessed threat produces Alert, which raises the soldier target to at least 50% after unlocking. Five consecutive completed turns at `critical` trigger Total War; counting is idempotent across repeated assessments in the same turn. HP strictly below 30% also triggers war if hostile ants are actually detected within the existing queen sensing radius. A single sighting does not immediately trigger war. Ten consecutive turns below `contact` end war, returning to Alert or Peace according to current threat. All thresholds are configurable.

Total War removes the paid production/upgrade reserve floor and requests soldiers every affordable production action after unlock. The existing paid upgrade cost/action, legal spawn checks, fractional Warfare costs, one queen action per turn and Production bonus queue remain unchanged. An existing queued bonus retains precedence; it is not silently converted into a different bonus. Negative reserves never fund births.

A strategy change issues a versioned message with only the queen's actually observed/reported target. The existing local-sensing/report model is extended by physical local relays: queen-to-ant within her existing sensing radius, then same-faction ant-to-ant within 2 Manhattan cells. One hop per completed turn uses a snapshot, preventing same-tick chain flooding. New targets and peace orders also require propagation. Distant ants do not read the current queen war state as an order; old messages can persist until newer ones arrive. Messages are passive information, like existing pheromone/report observations, not an extra combat or construction action. Existing local combat/pheromone behavior and queen threat alarms remain.

Notified soldiers advance toward known war targets and use normal local combat. Notified workers support those targets and existing construction; at least `ceil(25% of workers)` remain assigned to food work by stable ID. Local combat still takes precedence. That food workforce is protected from cooperative construction recruitment and the remote near-base defense override. V2 has no depot-to-queen hauling role. No target is invented when the queen has no observed/reported location. Queen death immediately clears queen strategy and existing ants' orders, stops production and retains all prior queenless rules.

## Supply Depot V2: globally linked food endpoints

This section supersedes the old physical depot inventory/hauling rules. It preserves the Phase 4F bounded navigation, Honeypots, 100-turn upkeep, signed reserves, strategic states, combat and physical soil/stone systems. It does not complete the separately pending event-loop responsiveness work.

### Cooperative construction and payment

Depots cost **exactly 15 food**, paid atomically from actual colony funds at project commitment. Peace/Alert retain the existing strategic reserve; Total War can spend below that allocation, but cannot pay from a negative/insufficient balance. Explicit `paid_half=30` prevents repeat payment. Construction expenditure is a food-accounting sink (`depot_spent_half`), not missing food. Abandonment/queen death does not refund this sunk expense. Completion costs nothing further.

The default **2x2 traversable footprint** consumes no soil and adds no ant capacity. All cells must be empty and free of food, living queens, stones, structures and other claims. At least two approach slots must exist. The entire pending footprint is claimed against structures/stones/new food; completion rechecks geometry and occupancy atomically. A temporarily occupied footprint waits with its paid work preserved.

Only living workers build depots. Each contributes **one work unit per completed turn**, consuming its one nonmovement action. Fewer than **two active builders** contributes zero work. Completion requires **20 units**: two workers take ten working turns; three take seven, supplying 21 units to pass the threshold. Duplicate crew IDs/repeated turn resolution cannot multiply work. Combat, death, illegal position or an already-used action disqualifies that worker. Soldiers/Honeypots cannot contribute.

Assignments and partial progress persist across travel, combat interruptions and temporary shortages. Depot projects are exempt from the 30-turn stone-job expiry. The default crew limit is four, retaining at least one harvester when three or more workers exist. If a paid project falls to two survivors, both can finish it. Autonomous proposals initially require three living workers. Assigned carriers finish their physical food delivery before building; immediate combat/defense/survival retain precedence, while new low-priority exploration and Honeypot errands cannot repeatedly steal empty builders. Shared approach fields, rotating movement arbitration and local steering retain existing occupancy limits. Stone and soil jobs retain their previous rules.

### Autonomous planning and configurable policy

Use only actually observed food positions, remembered quantities and observed regeneration classes. These records remain with their observer until physically relayed to nearby allies. Depot proposals read only the proposing ant's observed/received food memory; the old instantaneous faction registry is no longer an AI input. Empty local observations update stock memory; renewable sites may remain useful. Stale observations are possible until revisited.

Once per faction per ten turns, evaluate at most four valuable sources and twelve nearby candidates. Defaults: one remembered source within radius eight, renewable sources or at least five remembered food units, minimum actual queen route distance four, candidate within three cells of source, friendly depot spacing six, and minimum actual delivery-route saving two. Compare existing friendly depots by exact static route cost; already-served regions lose priority. Check legal footprint, actual source/worker reachability and locally observed enemy/foreign-signal risk. Favor discovered useful regions; no absolute-center requirement or hidden-food lookup exists.

A useful reachable proposal can make a **Peace** queen save 15 additional food for up to **150 turns**. This is a production allocation policy within the existing balance, not a separate inventory or change to the strategic-reserve formula. Paid births/upgrades retain that planned construction budget temporarily. Free Production births, upkeep, healing and starvation keep their rules. Alert adds no optional construction savings floor; Total War removes it immediately and keeps soldier priority. Expiry or queen death releases the plan; later valid evidence can renew saving. Payment still requires actual funds plus the applicable strategic floor. This prevents ordinary reproduction from indefinitely spending the build budget first.

Defaults in `config.py`: `depot_food_cost=15` (validated fixed), footprint `(2,2)`, builder limit 4, savings window 150, candidate limit 12, proposal interval 10, friendly spacing 6, home route threshold 4, food radius 8/minimum sources 1, useful saving 2. These are AI policy settings, not ant-population limits.

### Food delivery and queenless behavior

Completed friendly depots are **deposit endpoints**, with no independent inventory. A worker physically arrives carrying food and uses one action: remove its actual cargo and credit exactly that amount once to its living queen's existing signed balance and receipt ledger. `Depot.deposited` is cumulative throughput only. It is never counted as inventory or made separately spendable. No depot pickup, depot-to-queen hauling, storage-capacity limit or virtual ration withdrawal remains. Soldiers still obtain physical source rations and Honeypot upkeep supply; they do not become transport workers.

Carriers compare exact shared, resumable shortest-path costs to their queen perimeter and completed friendly depot footprints. Geometric distance only prunes candidates that cannot win. Pending searches wait legally; unreachable routes are excluded. Equal-cost ties retain the current valid depot. Terrain changes, newly completed depots and connection changes trigger reevaluation; transient ant congestion stays local. Enemy and unfinished depots cannot accept food.

Existing ordering puts deliveries before reproduction, scheduled upkeep and queen survival. Depot receipts are immediately available for upgrades, births, healing, upkeep and strategic accounting. Upkeep remains current-tile source, friendly living Honeypot, own cargo, shared signed reserve, then unchanged debt/starvation. Food and soil conservation are audited independently.

Depots remain indestructible faction structures: no HP, capture, repair, dismantling or independent reproduction/healing. Queen death **disconnects** them and rejects subsequent deposits; there is no local depot food to eat. Historical signed colony stock retains the existing queenless economy behavior. Survivors still consume real sources/cargo, receive Honeypot supply, lose HP on the existing schedule and attack enemies. No queen, perk or economy is resurrected. Paid unfinished projects cancel after queen death, retaining their sunk expense.

### Inspection, validation and limitations

Sites have an amber diagonal/progress bar; completed depots have faction outlines and a pale crossbar. Close zoom labels show work/builders or connection. Click a footprint to inspect progress/20, active/assigned workers, paid cost and blocked reason, or depot ownership, connection, cumulative receipts and shared balance. Ant/station click priority, all controls/cameras/overlays remain. Reset clears site/depot inspection.

```powershell
cd D:\Codex\ant\source
.\.venv\Scripts\python.exe main.py --size 512 --seed 7
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m benchmarks.depot_v2 --output work\depot-v2 --size 512 --turns 350 --seeds 7 19 42
.\.venv\Scripts\python.exe -m benchmarks.honeypots --part gameplay --output work\depot-v2-performance.jsonl
```

Validation uses unmodified normal initialization, no inserted depots/resources, three seeds, per-turn food/soil/occupancy audits and actual construction/delivery screenshots. Logs include proposals, accepted/completed jobs, first completion, actual builder contributions, depot/queen throughput, failure reasons and balance histories. Bounded fields can delay distant plans; persistent occupied/invalid paid sites can stall rather than lose work or bypass occupancy. Site/crew selection is heuristic, not globally optimal. Long-lived site claims are intentional until completion or queen death. No new destruction or save-game migration is provided.


## Direct-source upkeep, Honeypot Ants and central exploration

This increment supersedes earlier personal-cargo-first descriptions. All strategic reserves, Total War, physical depots, combat, soil, 100-turn timing and current Phase 4F navigation work remain. Ordinary worker/soldier carrying capacity and existing perks do not change.

### Upkeep priority and exact accounting

At each **100 completed turns**, living workers/soldiers pay the unchanged progressive cost. Exclude Honeypots entirely from the bracket population: they cost zero and cannot push a worker/soldier into a higher bracket. Process factions in numeric order, then ants in ascending ID. For each ant use:

1. Food physically at its current tile: ordinary sources, trophies, public stations and neutral death drops, in existing ordinary/drop-before-station source order.
2. Alive friendly Honeypots within **10 Manhattan cells** (no additional line-of-sight/path condition), nearest first and lower ID on ties; use multiple suppliers if needed, always decrementing finite stock.
3. That ant's existing cargo.
4. Actual signed queen reserve; unpaid amounts retain existing debt and starvation behavior.

Source extraction goes directly to upkeep, never into cargo. A sufficient source leaves already carried food unchanged. It uses existing depletion/respawn logic (ordinary downgrade after 25 turns, public refill schedule, nonrenewing drops/trophies). It is consumption rather than harvesting, so creates no Greed collection credit. The source and supplier ledgers are subsets of total upkeep, never additional consumption counted twice. Metabolism remains automatic, not an extra nonmovement action.

Queen healing still uses actual positive queen reserves, and signed debt/starvation penalties remain unchanged. V2 depot receipts already belong to the shared reserve; depots are not ordinary Food sources or separate inventories. The existing action/turn ordering remains: prior movement, actions/delivery, reproduction, upkeep, queen survival. Thus source quantity is sampled when settlement actually runs, after earlier actions in that turn.

### Confirmed Honeypot unit

| Attribute | Rule |
|---|---|
| Queen production cost | Exactly **5 food** / 10 half-units, paid from actual queen funds |
| HP | 15 |
| Movement | 1 cell per turn |
| Damage / harvesting | 0; cannot attack, harvest or perform construction |
| Upkeep | 0, including on food tiles |
| Stored food | Separate `stored_food` inventory, capacity **10** |
| Supply range | **10 Manhattan cells**, friendly living ants only |

Speed/Blitz do not speed it up; Heavy Lifting does not increase its confirmed storage. Sensitivity retains the existing local sensing convention (3 rather than 2 cells). Ordinary worker/soldier discounts and Production bonus milestones remain unchanged; no Honeypot receives a discount or free birth, because every one must cost exactly five. Empty Honeypots are born with zero stored food. They remain ordinary combat targets and can be killed; a zero-damage unit never consumes an attack action or generates a fake attack statistic.

Prototype automatic production policy: after the queen's existing upgrade, at least 6 living workers, target `ceil(workers / 20)` Honeypots. The 6/20 thresholds are configurable economic policy, not an ant population cap. Produce one only when five food plus the applicable strategic reserve is affordable; otherwise ordinary affordable production continues. Existing queued worker/soldier bonuses retain precedence. Total War keeps soldier priority and does not replace a wartime soldier birth with a Honeypot. Existing legal spawn and one queen production/upgrade action per turn remain unchanged. Honeypots are excluded from the worker/soldier strategic reserve population but are counted separately in total populations and the UI.

### Physical loading and autonomous behavior

Workers with harvested cargo may choose a friendly Honeypot advertised within the configurable local follow/loading-observation radius (default 10). They use shared shortest-static-cost fields to reach cardinal loading positions; only trips that beat the queen's geometric lower bound by more than 2 cells are candidates. A lower-bound prune avoids unnecessary searches; the chosen actual route still obeys static terrain, local occupancy and movement budgets. Nearby reservations reduce over-assignment. Actual adjacent loading costs the worker one action, transfers at most available space and leaves any excess cargo with that worker. No stock appears in the queen or a depot. Depot-origin/queen-bound cargo does not loop into a Honeypot.

Honeypot states are explicit: `honeypot-follow`, `honeypot-hold`, `honeypot-reposition`, `honeypot-retreat`. It follows locally observed expedition workers, holds near carriers to allow physical loading, repositions toward locally observed underserved friends or a previously communicated waypoint, and retreats from enemies detected through existing local combat sensing. It does not read undiscovered food or remote enemy positions. If the only escape approaches the sensed enemy, it holds; blocked retreat steps wait rather than choose an unsafe congestion sidestep. Slow units may fall behind faster expeditions; there is no teleportation or speed exception.

Queen death retains its fixed storage, clears existing war orders/perks as before, and applies existing queenless hunger (1 HP every five turns). A wounded queenless Honeypot can use its own stored food for normal 1-food/1-HP healing, capped at 15 and using one action. It does not harvest sources for healing and never attacks, including while queenless. Other queenless ants keep their established behavior and may receive upkeep supply from living friendly Honeypots.

### Neutral death drops

A dead Honeypot transfers **all remaining stored food** to neutral `drop` Food; it does not generate new food or add to the death/perk-loss waste counter. Empty bodies drop nothing. Ordinary ant death cargo remains waste under the existing rule.

Prefer the death tile if traversable and not an existing food site or structure. Otherwise choose nearest valid placement in deterministic Manhattan-ring/coordinate order. Never overwrite, convert or delete an existing source to place the drop. Ant occupancy does not prevent food placement because food occupies no ant slot; queens, stones, depots and pending footprints are protected. Drops are exempt from initial ordinary-source spacing so material can be placed near the death. Every faction may discover and harvest them, or consume them at upkeep. Their prototype scent radius is 4, propagating through actual terrain like other Food. They never respawn/downgrade or award Greed credits; exhausted drop records are removed on the next ecology tick.

Exceptional placement work is resumable with a default 256 candidate checks per call. If no immediate valid position can be found within that budget, the exact quantity remains in a physical pending-drop ledger, included in conservation, until deterministic placement completes. A completely invalid/full map cannot produce an immediately collectible legal drop; pending material retries rather than vanishing or overlapping an existing source. This is an explicit pathological-placement limitation. No RNG is consumed for placement. Reset clears units, drop food and pending-drop state.

### Bounded frontier and central expeditions

Survey actual friendly positions into sparse **8x8 terrain chunks**, incrementally maintaining adjacent unvisited frontiers. This survey registry contains terrain visits, not undiscovered food or enemy positions. After turn **10**, at most `ceil(20% of workers)` (and always fewer than all workers) form scouts, using stable IDs. Strong near-base defense and Total War suspend expedition assignment; cargo return, reporting, active construction, local combat and survival keep precedence. Remaining workers retain harvesting/logistics duties.

Scouts split between frontier exploration and central geographic expeditions. Each faction has at most **two coordinated shared routes**, one of each kind, with 24-turn commitments and distinct faction center approach regions. Progress advances chunk waypoints without reading hidden resources. Actually sensed ordinary food and genuine scent gradients can interrupt exploration; scouts avoid being trapped in repeated public-station delivery circuits. Failed chunks receive the existing 25-turn cooldown. Local waypoint terrain checks cover only one chunk; fields reuse Phase 4F static/dynamic separation, fixed node budgets and bounded deterministic cache. No full-map scan is added per ant or rendered frame.

The initial independent-waypoint prototype caused heavy cache churn (1,924 field builds in a 500-ant/20-turn profile). Coordinated routes reduced that same workload to 41 builds, retaining bounded work. Many mobile Honeypot targets can still increase cache pressure; no sensing frequency, combat, population or timing rule is reduced to mask that cost.

The UI displays W/S/H counts, queen food separately from Honeypot stock, a gold-filled Honeypot body, and selected-unit storage/state. Existing controls/camera/overlays remain observational. No new full information overlay or unrelated phase is introduced.

```powershell
cd D:\Codex\ant\source
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
New-Item -ItemType Directory -Force work | Out-Null
.\.venv\Scripts\python.exe -m benchmarks.honeypots --output work\honeypots.jsonl
.\.venv\Scripts\python.exe -m benchmarks.capture_honeypots --output-dir work\honeypot-demo
.\.venv\Scripts\python.exe main.py --size 128 --seed 7
```

`honeypots_enabled=True` controls automatic production. `exploration_enabled=True` controls expedition assignment. Normal games enable both; confirmed unit attributes/cost/range remain fixed. Configurable prototype defaults are the 6-worker/20-worker production policy, local follow radius 10, drop scent 4 and placement budget 256, exploration start 10/fraction 0.20/chunk size 8/commitment 24. The original design/reference files remain unchanged; this section documents the approved additions and superseding rules.


## Performance-first autonomy and physical information relay

Workers, soldiers and Honeypots all observe and carry food, enemy, danger, route, useful excavation and supply information. `systems/information.py` extends the existing passive local communication pass; it does not consume a second game action or credit food. There is no instantaneous faction food/enemy registry. Static terrain and friendly completed infrastructure retain their existing public navigation status. Faction survey coverage is observational; frontier selection uses the leader's own surveyed chunks and bounded adjacent geography.

Each ant holds at most **12 facts**, **24 deduplication entries** and **24 food observations/known food coordinates**. Facts retain their original observation time across hops. Food/route facts expire after 128 turns, enemy/danger after 16, and excavation/supply after 32. Food quantity changes are throttled to four-turn updates; locally observed depletion is immediate. Peers compare lightweight versions/content and do not repeatedly rebroadcast identical valid content. Contact probing rotates deterministically through crowded spatial buckets rather than scanning all ant pairs.

Defaults: radius 2 (the existing ant communication radius), one scheduled sender phase every **4 turns**, at most **16 examined spatial entries**, **2 recipient candidates** and **2 message intents per sender**, with **128 accepted events per turn** globally. A read-before-write snapshot prevents same-turn multi-hop flooding. New versions propagate over later physical contacts; no food/enemy coordinates are invented. Queenless ants keep local gossip while their queen orders, perks and reproduction remain disabled. Existing queen-order versions still travel through their original physical sensing/relay rules.

`ai/behavior.py` provides committed local frontier/patrol/escort tasks and up to four distributed queen guard posts per faction. Immediate combat, defense, survival, active construction and food delivery retain priority. Received enemy positions are last-known sightings, never live remote tracking. Soldiers still cannot perform ordinary food delivery. Honeypots retain all fixed costs, HP, load, zero-upkeep and death-drop rules; their nonurgent support choices are staggered while retreat and loading remain immediate.

Nonurgent planning runs in deterministic **8-turn ID phases**, doubling to 16 at 1,000 living ants. There are at most **8 new local patrol/frontier assignments**, **8 new shared expedition assignments** and **4 exceptional local path retries** per turn. Existing useful assignments survive births and routine updates. Shared expeditions retain at most two geographic route fields per faction. Local patrols normally steer through cardinal available cells without an independent global search. A legitimate planning wait or guard hold is not an idle failure.

Received excavation advice is actionable only for an adjacent ordinary-soil cell with actual traffic at the existing busy-path threshold, by an eligible worker on its planning phase. At most one such advice task per faction is accepted each turn. Real congestion excavation remains immediate under existing rules. Automatic filling no longer narrows widened passages; manual physical fill, reinforcement strength and soil conservation remain unchanged. Existing cheap stone/material handling stays intact. A larger autonomous fortification planner is deliberately deferred rather than adding unmeasured AI cost.

The shared navigation cache is now **48 fields**, increased from 24 after measuring cache churn. The **65,536-node turn budget, 64-job queue and 256-node quantum remain unchanged**. Fields still ignore transient occupancy and use localized static invalidation. Depot delivery considers lower-bound-sorted endpoints and skips a search only when an exact known path cost proves it cannot win. Pending distant candidates cannot suspend an already proven shortest nearby endpoint. Cached distance arrays can use about 48 MiB plus queue/dependency overhead; this is an explicit CPU/memory tradeoff.

Ant inspection now shows **Activity**, cached-fact count, last physical relay/contact, total stationary turns and unproductive idle turns separately. Productive actions/relay, strategic holds, dependency waits, temporary blockage and actual idle are distinct. More Information overlays remain observational. The main event loop remains synchronous; these changes do not claim an asynchronous engine or guaranteed input latency.

```powershell
cd D:\Codex\ant\source
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m benchmarks.autonomy --output work\autonomy-validation\AUTONOMY_AFTER.jsonl
.\.venv\Scripts\python.exe -m benchmarks.autonomy_replay --output work\autonomy-validation
```

The replay command expects `AUTONOMY_AFTER.jsonl` from a matching benchmark in its output directory. Raw benchmark records include mean/median/p95/worst timings, actual populations and casualties, stationary classes, explored cells, food/depot throughput, communication counts, construction, stuck/oscillation proxies, navigation counters and conservation audits. Three ordinary 512x512 seeds run for 500 completed turns; isolated tests do not substitute for these games. Read the delivered performance report for measured tradeoffs and limitations.
