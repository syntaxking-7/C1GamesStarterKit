## Game Rules: Citadel Terminal

Terminal (often referred to as Citadel Terminal or C1Games Terminal) is an AI programming competition created by Correlation One. It’s essentially a mix between a tower defense game and an auto-battler, played entirely through code.

Since you've been deep in the Python strategy, here is the high-level context of the game mechanics, the board, and why the math in your code works the way it does.

The Objective
You and your opponent start with 30 health points. The goal is to get your mobile units to cross the board and step on the opponent's absolute edge. Every unit that makes it across deducts 1 point from their health.

The Board
The game is played on a diamond-shaped grid.

You own the bottom half of the diamond (y-coordinates 0 to 13). You can only build stationary defenses here.

Your opponent owns the top half (y-coordinates 14 to 27).

The "edges" are the absolute bottom left and bottom right borders of the diamond. This is where your opponent's units are trying to go, and where you were trying to place those final turrets.

The Resources
You manage two different economies simultaneously. Both generate automatically every turn.

Cores (Structural Points / SP): You use these to build your stationary base.

Bits (Mobile Points / MP): You use these to spawn mobile attack units.

The Units
Stationary Defenses (Built with Cores/SP):

Turrets (Destructors): They shoot and deal damage. This is why your code prioritizes them at the choke points.

Walls (Filters): Cheap blocks used to force enemy units to walk down specific, longer paths (maze-building).

Supports (Encryptors): They provide a shielding aura to your mobile units when they spawn, or buff your other defenses. Your strategy uses them at the center (13,8 / 14,8) to buff your outgoing scouts.

Mobile Attackers (Spawned with Bits/MP):

Scouts (Pings): Fast, cheap, low health. They are meant to swarm and overwhelm defenses. Your R1-R3 strategy relies heavily on dumping MP into Scouts to find the path of least resistance.

Demolishers (EMPs): Slow, tanky, and prioritize destroying enemy structures.

Interceptors (Scramblers): Designed to hunt down and kill other mobile units.

The Game Loop (How Turns Work)
Both players' Python scripts run at the exact same time. You don't take turns; it happens simultaneously.

The Build Phase: The engine looks at where you placed your Turrets/Supports and deducts your Cores.

The Spawn Phase: The engine looks at where you deployed your Scouts and deducts your Bits.

Action Frames: The engine calculates the physics—units move along the shortest path to the enemy edge, turrets fire, units die.

End of Turn: The engine packages everything that just happened (spawns, deaths, damage) into the JSON turn_state and hands it back to your Python script for the next round.


---

## Strategy

### PART 1 — THE DEFENSIVE ENGINE (Structure Points)

#### Layer 1: Core Maintenance — The Heartbeat
Before anything else happens from Round 2 onward, the bot performs a "health check" on its core base. This core consists of eight units arranged in a tight cluster:
Four Supports at positions [13,8], [14,8], [13,7], and [14,7] — these form the power backbone of your base, providing shield bonuses to nearby turrets and dramatically increasing their effective HP.
Four Turrets at positions [13,9], [14,9], [12,7], and [15,7] — these flank the supports symmetrically, creating overlapping fire coverage.
If the opponent destroyed any of these eight units during the previous round, rebuilding them is the bot's absolute first action, consuming SP before any other placement decision is even considered. This is non-negotiable priority. The logic here is sound: a damaged core is an exponentially weaker core, because the turrets lose their support bonuses and the entire structure becomes vulnerable to snowball destruction. Paying the rebuild cost immediately is almost always worth it because the alternative — leaving the core broken — compounds into a catastrophic structural deficit.

#### Layer 2: The Opening Script (Rounds 1–3) — Discipline Over Improvisation
The first three rounds follow a rigid, handcrafted script rather than any dynamic logic. This is intentional. In the early game, you have almost no information about your opponent's strategy, so adaptive algorithms would be guessing blindly anyway. A disciplined opening is strictly superior to a flexible but uninformed one.
Round 1 is entirely about construction. The bot places all four core supports and all four core turrets to establish the base. Immediately after placement, it upgrades three of the four supports — [13,8], [14,8], and [13,7] — because upgraded supports provide significantly more shield throughput and the SP cost is most efficient to pay early before the opponent's attack paths are even established.
Round 2 upgrades the final support at [14,7], completing the fully upgraded core. More importantly, this is when the bot reads its first real piece of intelligence: it looks at exactly where the opponent attacked in Round 1 — specifically, the cell where their units penetrated deepest into your territory — and feeds that location into the Wall/Path Defense system (explained below) to respond to it surgically.
Round 3 repeats the reactive logic: it reads where the opponent attacked in Round 2 and again triggers the Wall/Path Defense against that zone. By the end of Round 3, the bot has now seen two rounds of enemy behavior, which is exactly enough data to feed the Predictive Engine.

#### Layer 3: The Predictive Engine (Round 4+) — Reading the Opponent's Mind
From Round 4 onward, the bot no longer reacts to the last attack — it predicts the next one. It stores a rolling memory of the opponent's last three attack locations (call them A, B, and C from oldest to newest) and pattern-matches against three behavioral archetypes:
The Spammer (A → A → A): If the opponent has hit the exact same zone three turns in a row, the bot concludes they have found a weak point and will continue exploiting it. It defends that same zone again. This pattern is the most common in less sophisticated bots and in players who find early success and over-commit to a single lane.
The Alternator (A → B → A): If the opponent has been bouncing back and forth between two zones, the bot recognises a ping-pong rhythm and predicts the next attack will go back to B (the most recent non-A location). This pattern often emerges when a player tries to bait defensive overcommitment on one side before slamming the other.
The Switch-Up (A → A → B): If the opponent spammed one side twice and then suddenly switched, the bot reads this as a feint. The logic is that a player who commits to one lane for two rounds has likely already invested in units and pathing for that side. The sudden switch to B was either a probe or a misdirection, and they will likely revert to their primary lane A. The bot defends A.
The Unknown (no pattern match): If the last three attacks don't fit any of the above shapes, the bot falls back to a pure simulation. It calculates the path your turrets would force enemy units to take from each of the six possible enemy spawn points, tallies up how much damage each path would absorb from your existing turrets, identifies the weakest path — the one that receives the least punishment — and pre-emptively reinforces that lane. This is the most computationally intensive branch but also the most robust, since it's grounded in actual board state rather than behavioral inference.

#### Layer 4: The Wall/Path Defense System — Surgical Placement
Once the bot knows which zone it needs to defend (whether from reactive reading in Rounds 2–3 or from prediction in Round 4+), it executes a precise, three-phase placement routine. This is the most tactically sophisticated part of the defense.
Phase 1 — The Absolute Edge (1 Turret): The bot identifies the final cell of the enemy's attack path — the tile immediately adjacent to your scoring wall — and places exactly one turret there. This turret will fire at full health on units that are already deep in your territory and nearly scoring. It's the last line of defense, placed deliberately so that even units who survive everything else will be punished at the finish line.
Phase 2 — The Choke Point (2 Turrets): The bot then looks exactly one Manhattan distance away from the edge turret and finds the cells that lie strictly on the enemy's predicted attack path. It places two turrets at these positions. These create a crossfire funnel: enemy units must pass through overlapping fire from the choke point turrets and the edge turret in rapid succession, giving your units multiple shots on the same target as it walks a gauntlet.
Phase 3 — The SP Dump (Remaining Points): Every single remaining SP is then spent walking backwards up the enemy's attack path from the choke point toward their spawn. The bot drops turrets directly on the path cells and immediately adjacent to them until SP hits exactly zero. This creates a cascading kill corridor — units take fire from the moment they enter your side of the board, and by the time they reach the choke point and edge turret, they have already been whittled down. The backwards-walk approach is crucial: it prioritises the deepest defensive positions (closest to your wall) first, so that even partial SP budgets are maximally efficient.

#### Layer 5: The AFK Fallback — What To Do With Nothing
There is one edge case: if the opponent has literally never spawned a single offensive unit, there is no attack path to defend. Rather than wasting SP on arbitrary placements, the bot wraps your four core supports in a dense protective shell of turrets, spending every available SP in a ring outward from the core. This ensures the SP is never wasted and keeps the base as hard as possible to crack when the opponent eventually does commit.

---

### PART 2 — THE OFFENSIVE ENGINE (Mobile Points)

#### Phase 1: The Opening Strike (Round 1) — Instant Pressure
Round 1's offense is completely hardcoded. The bot immediately deploys exactly 5 Scouts from position [13,0] — a dead-center launchpad. This opening is chosen for three reasons: it applies immediate board pressure before the opponent has any defenses up, it requires zero computation time (freeing all processing for the complex base build), and most importantly, it permanently logs [13,0] into memory as the "Last Used Launchpad," seeding the ban system for Round 2.

#### Phase 2: The Memory Ban System (Round 2+) — Turning Defense Into Waste
This is the single most game-changing mechanic in the offensive engine. At the start of every round from Round 2 onward, before any simulation or decision-making, the bot does one thing: it permanently removes the previous turn's launchpad from the candidate list.
The strategic logic is airtight. When your Scouts hit from the left side, a rational opponent will immediately spend their entire SP budget building a wall of turrets on the left to counter the threat. That wall is expensive. If you attack from the left again, it was money well spent — they shut you down. But if you never attack from the same side twice in a row, their freshly built wall sits idle, guarding an empty lane while your Scouts pour through an undefended corridor on the opposite side. You have converted their SP into wasted resources. Every SP they spend reacting to your last move is SP that can't protect them from your next one.
The ban is unconditional and mechanical — it requires no decision-making and cannot be overridden. This prevents any edge case where the simulation might naively select the previously used launchpad because it happens to look slightly safer. The ban is absolute.

#### Phase 3: The Fast-Math Simulation — Finding the Safest Route
With one launchpad banned, the bot now has exactly five candidates. For each one, it runs a lightweight path simulation:
It scans the entire arena for every enemy turret currently on the board. It then walks the exact path a Scout would take from that launchpad — following Terminal's pathfinding rules — and at each step checks whether any enemy turret falls within 2.5 tiles of the Scout's current position. Rather than computing actual square roots (which are slow), it uses squared-distance math (checking if the distance squared is ≤ 6.25) for instant comparisons. Each "in-range turret encounter" adds to that launchpad's Damage Score.
After all five paths are scored, the bot selects the launchpad with the lowest Damage Score — the route where your Scouts absorb the least punishment on their way through.

#### Phase 4: The Maximum Swarm — All-In Execution
Once the safest launchpad is identified, the bot counts your entire MP bank and converts 100% of it into Scouts launched from that position. No reserves, no hedging. The reasoning is mathematical: Scouts are the most MP-efficient unit for breaching lightly defended lanes, and a large wave of Scouts is exponentially more effective than a small wave because enemy turrets can only fire so many times per round. A swarm of 15 Scouts in an undefended lane is nearly always a scoring run.
Finally, the just-used launchpad is written to memory, automatically becoming the banned launchpad for the next round. The cycle is self-perpetuating.

### How the Two Engines Interact
The defense and offense don't directly communicate, but they are implicitly coordinated through timing. Defense resolves completely first — all SP is committed, the core is repaired, the predicted path is fortified — and only then does the offense run. This matters because:
Your defensive placements can accidentally block or redirect your own Scouts' paths if placed carelessly. By resolving defense first and letting the offensive simulation run afterward, the bot's path simulation always sees the final, committed board state and routes Scouts around your own structures correctly.
Additionally, the pattern predictor and the launchpad ban system both work on a shared principle: never be predictable in the same way twice. The defense anticipates the opponent's pattern; the offense breaks its own pattern. Together, they create an asymmetric information advantage — you are harder to read than your opponent, and you are actively reading them.