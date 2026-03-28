import gamelib
import random
import math
import warnings
from sys import maxsize
import json


"""
Predictive Defense + Launchpad Ban System Bot
=============================================
Implements the full strategy from CONTEXT.md:
  - 5-Layer Defensive Engine (SP/Structure Points)
  - 4-Phase Offensive Engine (MP/Mobile Points)
"""


class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

        # ── Core base positions ──
        self.core_supports = [[13, 8], [14, 8], [13, 7], [14, 7]]
        self.core_turrets = [[13, 9], [14, 9], [12, 7], [15, 7]]

        # ── Predictive Engine state ──
        self.attack_history = []        # Rolling memory of last 3 attack zones
        self.last_attack_location = None  # Deepest enemy penetration this turn

        # ── Offense: Memory Ban System ──
        self.all_launchpads = [
            [13, 0], [14, 0],   # Center bottom
            [2, 11], [25, 11],  # Wide flanks
            [7, 6],  [20, 6],   # Mid flanks
        ]
        self.last_launchpad = None  # Banned for next round

    # =====================================================================
    # FRAMEWORK HOOKS
    # =====================================================================
    def on_game_start(self, config):
        gamelib.debug_write('Configuring Predictive Defense + Ban System Bot...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0

    def on_turn(self, turn_state):
        game_state = gamelib.GameState(self.config, turn_state)
        game_state.suppress_warnings(True)

        # Cache turret damage once (avoid repeated GameUnit instantiation)
        if not hasattr(self, 'cached_turret_damage'):
            self.cached_turret_damage = gamelib.GameUnit(
                TURRET, game_state.config
            ).damage_i

        self.execute_strategy(game_state)
        game_state.submit_turn()

    def _safe_find_path(self, game_state, location):
        """Wrapper around find_path_to_edge that avoids the pathfinder's
        infinite loop when the start location is blocked or out of bounds."""
        if not game_state.game_map.in_arena_bounds(location):
            return None
        if game_state.contains_stationary_unit(location):
            return None
        try:
            return game_state.find_path_to_edge(location)
        except Exception:
            return None

    # =====================================================================
    # MAIN STRATEGY DISPATCHER
    # =====================================================================
    def execute_strategy(self, game_state):
        """Resolve defense (SP) completely first, then offense (MP)."""
        turn = game_state.turn_number
        current_attack = self.last_attack_location

        # ── SP PHASE (DEFENSE) ──
        if turn >= 1:
            self.rebuild_core(game_state)           # Layer 1

        if turn == 0:
            self.round_1_defense(game_state)        # Layer 2
        elif turn == 1:
            self.round_2_defense(game_state, current_attack)
        elif turn == 2:
            self.round_3_defense(game_state, current_attack)
        else:
            self.predictive_defense(game_state, current_attack)  # Layer 3

        # Reset for next turn's tracking
        self.last_attack_location = None

        # ── MP PHASE (OFFENSE) ──
        if turn == 0:
            self.round_1_offense(game_state)        # Phase 1
        else:
            self.execute_offense(game_state)        # Phases 2–4

    # =====================================================================
    # LAYER 1: CORE MAINTENANCE  —  Non-negotiable rebuild priority
    # =====================================================================
    def rebuild_core(self, game_state):
        """Rebuild any destroyed core units before anything else."""
        # Supports first (they buff turrets)
        for loc in self.core_supports:
            if not game_state.contains_stationary_unit(loc):
                game_state.attempt_spawn(SUPPORT, loc)
                game_state.attempt_upgrade(loc)

        # Turrets second
        for loc in self.core_turrets:
            if not game_state.contains_stationary_unit(loc):
                game_state.attempt_spawn(TURRET, loc)

    # =====================================================================
    # LAYER 2: OPENING SCRIPT  —  Rounds 1–3
    # =====================================================================
    def round_1_defense(self, game_state):
        """Round 1: Build full core + upgrade first 3 supports."""
        for loc in self.core_supports:
            game_state.attempt_spawn(SUPPORT, loc)
        for loc in self.core_turrets:
            game_state.attempt_spawn(TURRET, loc)

        # Upgrade [13,8], [14,8], [13,7]
        for loc in [[13, 8], [14, 8], [13, 7]]:
            game_state.attempt_upgrade(loc)

    def round_2_defense(self, game_state, current_attack):
        """Round 2: Upgrade final support, react to Round 1 attack."""
        game_state.attempt_upgrade([14, 7])

        if current_attack:
            self.wall_path_defense(game_state, current_attack)
            self.update_attack_history(current_attack)
        else:
            self.afk_fallback(game_state)

    def round_3_defense(self, game_state, current_attack):
        """Round 3: React to Round 2 attack."""
        if current_attack:
            self.wall_path_defense(game_state, current_attack)
            self.update_attack_history(current_attack)
        else:
            self.afk_fallback(game_state)

    # =====================================================================
    # LAYER 3: PREDICTIVE ENGINE  —  Round 4+
    # =====================================================================
    def predictive_defense(self, game_state, current_attack):
        """Predict opponent's next attack via pattern matching."""
        if current_attack:
            self.update_attack_history(current_attack)

        predicted_zone = self.predict_attack_zone(game_state)

        if predicted_zone:
            self.wall_path_defense(game_state, predicted_zone)
        else:
            self.afk_fallback(game_state)

    def update_attack_history(self, location):
        """Maintain rolling memory of last 3 attack zones."""
        zone = self.location_to_zone(location)
        self.attack_history.append(zone)
        if len(self.attack_history) > 3:
            self.attack_history.pop(0)

    def location_to_zone(self, location):
        """Bucket a location into left / center / right."""
        x = location[0]
        if x < 10:
            return 'left'
        elif x > 17:
            return 'right'
        else:
            return 'center'

    def predict_attack_zone(self, game_state):
        """Pattern-match against behavioral archetypes."""
        if len(self.attack_history) < 3:
            return self.find_weakest_lane(game_state)

        A, B, C = (self.attack_history[-3],
                    self.attack_history[-2],
                    self.attack_history[-1])

        # Spammer: A → A → A  (same zone 3×)
        if A == B == C:
            return self.zone_to_representative_location(A)

        # Alternator: A → B → A  (ping-pong) → predict B next
        if A == C and A != B:
            return self.zone_to_representative_location(B)

        # Switch-Up: A → A → B  (feint) → predict revert to A
        if A == B and B != C:
            return self.zone_to_representative_location(A)

        # Unknown: simulation fallback
        return self.find_weakest_lane(game_state)

    def zone_to_representative_location(self, zone):
        """Map a zone name to a representative board coordinate.
        These must be open cells that won't conflict with our core structures."""
        if zone == 'left':
            return [3, 12]
        elif zone == 'right':
            return [24, 12]
        else:
            return [14, 0]

    def find_weakest_lane(self, game_state):
        """Simulate paths from all enemy spawn points; return weakest."""
        enemy_spawns = [
            [13, 27], [14, 27],
            [0, 14],  [27, 14],
            [6, 21],  [21, 21],
        ]

        min_damage = float('inf')
        weakest_spawn = None

        for spawn in enemy_spawns:
            path = self._safe_find_path(game_state, spawn)
            if not path:
                continue

            damage = 0
            for loc in path:
                attackers = game_state.get_attackers(loc, 0)
                damage += len(attackers) * self.cached_turret_damage

            if damage < min_damage:
                min_damage = damage
                weakest_spawn = spawn

        if weakest_spawn:
            path = self._safe_find_path(game_state, weakest_spawn)
            if path:
                # Deepest point in our territory (y ≤ 13)
                for loc in reversed(path):
                    if loc[1] <= 13:
                        return loc

        return None  # No valid lane found

    # =====================================================================
    # LAYER 4: WALL / PATH DEFENSE  —  Surgical turret placement
    # =====================================================================
    def wall_path_defense(self, game_state, target_location):
        """Three-phase turret corridor along the predicted attack path."""
        path = self._safe_find_path(game_state, target_location)
        if not path:
            self.afk_fallback(game_state)
            return

        # Only cells in our territory
        our_path = [loc for loc in path if loc[1] <= 13]
        if not our_path:
            self.afk_fallback(game_state)
            return

        turrets_placed = 0
        sp_cost = game_state.type_cost(TURRET)[SP]

        # Phase 1 — Edge turret (1 turret at deepest point)
        edge_loc = our_path[-1]
        for loc in self._adjacent_cells(edge_loc, game_state):
            if turrets_placed >= 1:
                break
            if (game_state.get_resource(SP) >= sp_cost
                    and not game_state.contains_stationary_unit(loc)):
                if game_state.attempt_spawn(TURRET, loc):
                    turrets_placed += 1

        # Phase 2 — Choke-point turrets (2 turrets one step back)
        if len(our_path) >= 2:
            choke_loc = our_path[-2]
            for loc in self._adjacent_cells(choke_loc, game_state):
                if turrets_placed >= 3:
                    break
                if (game_state.get_resource(SP) >= sp_cost
                        and not game_state.contains_stationary_unit(loc)):
                    if game_state.attempt_spawn(TURRET, loc):
                        turrets_placed += 1

        # Phase 3 — SP dump (walk backwards up path from choke→spawn)
        for i in range(len(our_path) - 3, -1, -1):
            if game_state.get_resource(SP) < sp_cost:
                break

            path_loc = our_path[i]
            candidates = [path_loc] + self._adjacent_cells(path_loc, game_state)

            for loc in candidates:
                if game_state.get_resource(SP) < sp_cost:
                    break
                if not game_state.contains_stationary_unit(loc):
                    game_state.attempt_spawn(TURRET, loc)

    def _adjacent_cells(self, location, game_state):
        """Return valid adjacent cells within our territory."""
        x, y = location
        out = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            loc = [x + dx, y + dy]
            if loc[1] <= 13 and game_state.game_map.in_arena_bounds(loc):
                out.append(loc)
        return out

    # =====================================================================
    # LAYER 5: AFK FALLBACK
    # =====================================================================
    def afk_fallback(self, game_state):
        """No attacks detected — ring turrets outward from core supports."""
        sp_cost = game_state.type_cost(TURRET)[SP]

        for radius in range(1, 6):
            for sx, sy in self.core_supports:
                for dx in range(-radius, radius + 1):
                    abs_dx = abs(dx)
                    remaining = radius - abs_dx
                    dy_vals = ([remaining, -remaining]
                               if remaining != 0 else [0])
                    for dy in dy_vals:
                        loc = [sx + dx, sy + dy]
                        if game_state.get_resource(SP) < sp_cost:
                            return
                        if (loc[1] <= 13
                                and game_state.game_map.in_arena_bounds(loc)
                                and not game_state.contains_stationary_unit(loc)):
                            game_state.attempt_spawn(TURRET, loc)

    # =====================================================================
    # OFFENSE  —  Phases 1–4
    # =====================================================================
    def round_1_offense(self, game_state):
        """Phase 1: 5 Scouts from [13,0], seed the ban system."""
        game_state.attempt_spawn(SCOUT, [13, 0], 5)
        self.last_launchpad = [13, 0]

    def execute_offense(self, game_state):
        """Phases 2–4: Ban → Simulate → Maximum Swarm."""
        if game_state.get_resource(MP) < 1:
            return

        # Phase 2 — Memory Ban: remove last used launchpad
        #           Also filter out any launchpads blocked by our own structures
        candidates = [lp for lp in self.all_launchpads
                      if lp != self.last_launchpad
                      and not game_state.contains_stationary_unit(lp)]

        if not candidates:
            # All launchpads blocked — fall back to any unblocked edge
            friendly_edges = (game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT)
                              + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT))
            candidates = [loc for loc in friendly_edges
                          if not game_state.contains_stationary_unit(loc)]
            if not candidates:
                return  # Nowhere to spawn

        # Phase 3 — Fast-Math Simulation: find safest route
        best_lp = self._find_safest_launchpad(game_state, candidates)

        # Phase 4 — Maximum Swarm: all MP into Scouts
        mp_available = int(game_state.get_resource(MP))
        game_state.attempt_spawn(SCOUT, best_lp, mp_available)

        # Store for next round's ban
        self.last_launchpad = best_lp

    def _find_safest_launchpad(self, game_state, candidates):
        """Score each candidate launchpad by cumulative turret damage."""
        best_score = float('inf')
        best_lp = candidates[0] if candidates else [13, 0]

        for lp in candidates:
            path = self._safe_find_path(game_state, lp)
            if not path:
                continue

            damage_score = 0
            for loc in path:
                # Count enemy turrets in range (squared-distance ≤ 6.25)
                attackers = game_state.get_attackers(loc, 0)
                damage_score += len(attackers) * self.cached_turret_damage

            if damage_score < best_score:
                best_score = damage_score
                best_lp = lp

        return best_lp

    # =====================================================================
    # ACTION FRAME HANDLER  —  Track enemy penetration
    # =====================================================================
    def on_action_frame(self, turn_string):
        """Track deepest enemy penetration into our territory."""
        state = json.loads(turn_string)
        events = state.get("events", {})

        # Breaches (enemy units that scored on us)
        for breach in events.get("breach", []):
            if len(breach) >= 4:
                loc = breach[0]
                if loc[1] <= 13:
                    self.last_attack_location = loc

        # Enemy movement — track deepest point (lowest y)
        for move in events.get("move", []):
            if len(move) >= 4:
                loc = move[0]
                owner = move[3] if len(move) > 3 else None
                if owner == 2 and loc[1] <= 13:
                    if (self.last_attack_location is None
                            or loc[1] < self.last_attack_location[1]):
                        self.last_attack_location = loc


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
