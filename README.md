Ant Colonies - Supply Depot V2 and Performance-First Autonomy

HOW TO PLAY
1. Double-click ant.exe in this folder.
2. Select New Game, choose a map size and seed, then select Start Game.
3. No Python installation or internet connection is required.

MOVING THE GAME
Move the entire ant folder to another location or Windows 64-bit computer.
Keep the _internal folder beside ant.exe. Do not move ant.exe on its own.
The game does not depend on the source folder or the original D:\Codex location.

CONTROLS
Space / Esc: Pause or resume
1 / 2 / 3 / 4: Select 1x / 2x / 4x / 8x speed
R: Restart; E: End the game
Mouse wheel: Zoom
Middle or right mouse drag: Pan
F: Cycle colony focus; Home / V: Full-map overview
Left click: Inspect ants, supply stations, depots and construction sites
S / P / C: Toggle food scent, pheromone trails and territory coverage

CONTENTS
ant.exe            Windows 64-bit game executable
_internal          Bundled Python, Pygame, NumPy and runtime dependencies; keep this folder
source             Complete source, tests, design documents and development notes
licenses           Third-party license notices
package-info.json  Package version and verification information
validation.json    Executable startup and relocation test results

VERSION NOTES
All existing Supply Depot V2 rules are preserved. A depot costs 15 food,
requires at least two workers and takes 20 worker-turn units of construction.
Once completed, deliveries credit the owning living queen's shared food balance.
No new gameplay features were added.
All 321 regression tests pass; see PERFORMANCE_REPORT.md for results. The executable also passed standalone startup
and relocation tests without Python on PATH.
The first launch may take longer than subsequent launches.
The executable is not code-signed.

SOURCE DEVELOPMENT
Use the source folder as your working directory. Prepare a Python environment
and install requirements.txt. Normal play only requires ant.exe.


From this folder: source\.venv\Scripts\python.exe source\main.py

AUTONOMY UPDATE
All ant types now relay locally observed information through nearby allies.
Guarding, planning waits and unproductive idle have separate inspection labels.
Combat, food, depots, Honeypots and construction rules are preserved.
