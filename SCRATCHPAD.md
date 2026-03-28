# Strategy Implementation Analysis

## BUG FIX: Infinite Loop Issue

### Root Cause
The `wall_path_defense` function calls `find_path_to_edge(target_location)` where `target_location` is in our territory. This returns the path **FROM our territory TO enemy edge** (upward), but we need the **enemy's attack path** (downward toward our scoring edge).

**Result:** 
- `our_path[-1]` is at y≈13 (boundary), not y≈0 (our edge)
- Turrets placed in wrong locations
- Path iteration logic breaks

### Fix
Rewrite `wall_path_defense` to:
1. Use target_location directly as the defense anchor point
2. Place turrets in concentric rings around the attack point
3. Prioritize cells closer to our edge (lower y values)

---

## Implementation Status: ✅ COMPLETE

---

## CORE POSITIONS (FIXED)
- **Supports:** [13,8], [14,8], [13,7], [14,7]
- **Turrets:** [13,9], [14,9], [12,7], [15,7]

---

## DEFENSE IMPLEMENTATION CHECKLIST

### Layer 1: Core Maintenance (Round 2+)
- [x] Check if any of 8 core units destroyed → `rebuild_core()`
- [x] Rebuild them FIRST before any other placement

### Layer 2: Opening Script (Rounds 1-3)
- [x] Round 1: Place 4 supports + 4 turrets, upgrade 3 supports → `round_1_defense()`
- [x] Round 2: Upgrade final support [14,7], react to Round 1 attack → `round_2_defense()`
- [x] Round 3: React to Round 2 attack → `round_3_defense()`

### Layer 3: Predictive Engine (Round 4+)
- [x] Track last 3 attack locations (rolling memory) → `update_attack_history()`
- [x] Pattern: Spammer (A→A→A) → defend A → `predict_attack_zone()`
- [x] Pattern: Alternator (A→B→A) → defend B → `predict_attack_zone()`
- [x] Pattern: Switch-Up (A→A→B) → defend A → `predict_attack_zone()`
- [x] Fallback: simulate paths, find weakest lane → `find_weakest_lane()`

### Layer 4: Wall/Path Defense System
- [x] Phase 1: 1 turret at absolute edge (end of path) → `wall_path_defense()`
- [x] Phase 2: 2 turrets at choke point (1 Manhattan from edge)
- [x] Phase 3: Dump remaining SP walking backwards up path

### Layer 5: AFK Fallback
- [x] If no attacks, ring turrets around core → `afk_fallback()`

---

## OFFENSE IMPLEMENTATION CHECKLIST

### Phase 1: Opening Strike (Round 1)
- [x] Deploy 5 Scouts from [13,0] → `round_1_offense()`
- [x] Store [13,0] as last used launchpad

### Phase 2: Memory Ban System (Round 2+)
- [x] Ban previous launchpad from candidates → `execute_offense()`
- [x] 6 spawn options: [13,0], [14,0], [2,11], [25,11], [7,6], [20,6]

### Phase 3: Fast-Math Simulation
- [x] For each non-banned launchpad, calculate damage score → `find_safest_launchpad()`
- [x] Uses `get_attackers()` for turret range detection

### Phase 4: Maximum Swarm
- [x] All MP into Scouts at safest location
- [x] Store used launchpad for next round's ban

---

## Data Structures Implemented
```python
self.core_supports = [[13, 8], [14, 8], [13, 7], [14, 7]]
self.core_turrets = [[13, 9], [14, 9], [12, 7], [15, 7]]
self.attack_history = []  # Rolling memory of last 3 attack zones
self.last_attack_location = None  # Current turn's attack location
self.all_launchpads = [[13, 0], [14, 0], [2, 11], [25, 11], [7, 6], [20, 6]]
self.last_launchpad = None  # Banned for next round
```

---

## Key Methods
| Method | Purpose |
|--------|---------|
| `execute_strategy()` | Main dispatcher by turn number |
| `rebuild_core()` | Layer 1: Rebuild damaged core units |
| `round_1_defense()` | Build core, upgrade 3 supports |
| `round_2_defense()` | Upgrade 4th support, react to attack |
| `round_3_defense()` | React to attack |
| `predictive_defense()` | Pattern matching + fallback |
| `wall_path_defense()` | 3-phase turret placement |
| `afk_fallback()` | Ring turrets around core |
| `round_1_offense()` | 5 Scouts from [13,0] |
| `execute_offense()` | Ban system + swarm |
| `on_action_frame()` | Track enemy attacks |
