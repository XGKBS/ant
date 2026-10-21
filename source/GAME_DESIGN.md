# Ant Colony Simulation — Game Design Document (V1.3)

## Purpose
Create a four-faction autonomous ant-colony simulation in Python/Pygame, based on the supplied `antSim(1).py` example. Factions: red, yellow, blue, green, each starting in one map corner with one stationary 2x2 queen and two workers. Default map: 512x512 logical cells, configurable. The game is autonomous, not individually player-controlled.

## Victory and lifecycle
The last surviving queen wins. A manually ended game or turn-limited game with multiple queens alive has no winner. When a queen dies, the faction cannot win, cannot reproduce, and loses its selected queen perk. Its surviving ants persist as a queenless colony: lose 1 HP every five simulation turns, can consume food directly to restore 1 HP per food unit (capped at worker 5 / soldier 12), and attack other factions on encounter. No resurrection after HP reaches zero. A dead queen drops a large food trophy; exact amount and scent range remain configurable/TBD. Ordinary dead ants drop nothing.

## Time and controls
One turn is one second at 1x. 1x/2x/4x/8x speed; animate continuous interpolation rather than teleporting. Each ant can move up to its speed in cells per turn and perform at most one nonmovement action per turn (dig, fill, stone move, food handling, or attack). Runtime menu: pause/resume, end, reset, optional positive maximum turn count (blank means unlimited), More Information overlays. Pause freezes logical turns and animation. Reset initializes a fresh simulation. End stops and preserves results.

## Ants
| Type | HP | Damage | Movement cells/turn | Sensing | Load | Capabilities |
|---|---:|---:|---:|---:|---:|---|
| Worker | 5 | 1 | 2 | 2 | 1 | dig, fill, stone teamwork, carry food, combat |
| Soldier | 12 | 3 | 3 | 3 | 1 | dig, fill, stone teamwork, combat; no ordinary food transport |
| Queen | 50 | 0 | 0 | 10 | n/a | receive food, upgrade, produce up to one ant/turn; cannot attack |

Soldiers in queenless colonies may eat food directly despite their prohibition on transporting it. Queen is stationary, occupies four cells, and cannot attack. Queen's alarm radius 10: foreign information within range raises alert and prioritizes soldiers; when seriously threatened, reachable colony members defend or build defenses.

## Terrain
Initial terrain: ordinary soil, stones, large stones; hardened soil is created by moving excavated soil to another soil cell. Ordinary soil is traversable by ONE ant at a time. Digging changes it to a widened passage with capacity FOUR ants per cell. All traversable cells have occupancy limits; crowded ants must wait/reroute. Soil stack strength = n^2 for n=1,2,3 (1,4,9); hardened soil cannot be dug again as described by the original rule. Soil removal/fill material accounting must be consistent. Stones and large stones cannot be destroyed; cooperative relocation requires enough ants and available destination footprint. Stone composition between stones via placement of five soil units is proposed. Example: combined two-cell stone weight 8; four ants at quarter normal speed, eight at normal speed. This example conflicts with a naive linear load/weight formula: implement an explicitly documented piecewise/interpolated rule preserving the given example, or ask for clarification before finalizing. Large-stone weight and footprint TBD.

## Food
| Type | Food units | Maximum scent radius (cells) |
|---|---:|---:|
| Micro | 1 | 2 |
| Small | 5 | 4 |
| Medium | 10 | 8 |
| Large | 25 | 16 |
| Trophy | TBD | TBD |

Scent expands each turn until its maximum radius; stronger nearer the source. Exhausted food sources respawn 25 turns later, one tier lower; behavior of exhausted micro source TBD. Every 50 turns add 4 small sources, every 75 turns add 2 medium sources, every 100 turns add 1 large source near the center. Distinct food sources must be at least 5 cells apart. Food must occupy accessible or eventually reachable locations. Workers deliver carried food to their own queen/base for production. Queenless ants consume food to heal; 1 unit heals 1 HP, never above maximum.

## Pheromones and autonomy
Conceptual per-cell information: `[side,toBase,toFood,block,toBattle,isBase,isFood]`. Factions cannot interpret foreign pheromones but detect their presence. Pheromone trails decay each turn, repeated use reinforces them. Persistent base/food facts should be grounded in world entities rather than blindly decayed. Food and battle trails guide movement. Workers explore, find food, cooperate to move loads, report unknown faction signals, and defend when warned. Queen assesses threat and dynamically adjusts worker/soldier production ratio, after upgrade. Threat-dependent ratios are recommendations, not finalized: safe 100/0, alert 75/25, contact 50/50, near-base 25/75, critical 0/100. Implement an explainable finite state machine, not random motion disguised as AI.

## Economy and perks
Queen produces at most one ant each turn if food allows. Initially workers cost 2 food, and queen may spend 10 food to upgrade and unlock soldiers; soldiers cost 2 food after upgrade. One pregame perk per faction:
- Production: after producing 10 workers, automatically upgrade; after upgrade every 10 same-type produced grants one bonus ant.
- Exploration: workers cost 1.5 food.
- Warfare: soldiers cost 1.5 food.
- Speed: workers move 3.
- Blitz: soldiers move 4.
- Greed: after collecting food from 5 sources of the same tier, the next respawn of that tier does not downgrade (exact counting semantics TBD).
- Heavy lifting: each ant's load becomes 1.5.
- Sensitivity: queen senses 15, workers sense 3.
Fractional costs must be handled deterministically (e.g. half-unit integer accounting).

## Combat
Worker damage 1, soldier damage 3, queen damage 0. A queen's death creates trophy food and a queenless colony. Ants from different factions may fight when within interaction range (range TBD). Queenless ants are hostile on detecting any other faction. No simultaneous-action ordering, combat targeting, or collision damage rules have been finalized.

## UI and visualization
More Information toggles separately: food scent radii/intensity, pheromone trails (base/food/battle distinguished), and colored faction influence/coverage. Visualizations are observational only, not new information accessible to ant AI. Show faction populations, food reserves, queen HP/status, turn, speed, and winner/no-winner outcome.

## Explicitly unresolved — do not silently invent final rules
Initial nest clearance; exact hardened-soil traversal/capacity; soil excavation deposit mechanics; stone speed curve, weights, rotation, movement footprint; food carry quantity and actions; trophy amount/scent; micro respawn; pheromone decay/reinforcement coefficients and signal types; threat scoring; combat targeting/order/range; queenless eating action timing and AI priority; whether queenless ants retain historical pheromone trails; tie handling when multiple queens die on same turn; food placement accessibility; territory influence definition. Use documented configurable defaults only where necessary for a working prototype and report them clearly.
