import gamelib
import random
import math
import warnings
from sys import maxsize
import json

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        
        # Core base positions (from strategy)
        self.core_supports = [[13, 8], [14, 8], [13, 7], [14, 7]]
        self.core_turrets = [[13, 9], [14, 9], [12, 7], [15, 7]]
        
        # Attack tracking for predictive engine
        self.attack_history = []  # Rolling memory of last 3 attack zones
        self.last_attack_location = None  # Most recent attack location this turn
        
        # Offense: Memory ban system
        self.all_launchpads = [[13, 0], [14, 0], [2, 11], [25, 11], [7, 6], [20, 6]]
        self.last_launchpad = None  # Banned for next round

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
        
        # Cache turret damage on first turn
        if not hasattr(self, 'cached_turret_damage'):
            self.cached_turret_damage = gamelib.GameUnit(TURRET, game_state.config).damage_i

        self.execute_strategy(game_state)
        game_state.submit_turn()

    def execute_strategy(self, game_state):
        """Main strategy dispatcher based on turn number."""
        turn = game_state.turn_number
        
        # Store current attack location before resetting (for use in defense)
        current_attack = self.last_attack_location
        
        # === SP PHASE (DEFENSE) ===
        if turn >= 1:
            # Layer 1: Core Maintenance - rebuild damaged core units FIRST
            self.rebuild_core(game_state)
        
        if turn == 0:
            # Layer 2: Opening Script - Round 1
            self.round_1_defense(game_state)
        elif turn == 1:
            # Layer 2: Opening Script - Round 2
            self.round_2_defense(game_state, current_attack)
        elif turn == 2:
            # Layer 2: Opening Script - Round 3
            self.round_3_defense(game_state, current_attack)
        else:
            # Layer 3: Predictive Engine (Round 4+)
            self.predictive_defense(game_state, current_attack)
        
        # Reset attack location for next turn's tracking
        self.last_attack_location = None
        
        # === MP PHASE (OFFENSE) ===
        if turn == 0:
            # Phase 1: Opening Strike
            self.round_1_offense(game_state)
        else:
            # Phase 2-4: Ban System + Simulation + Swarm
            self.execute_offense(game_state)

    # =========================================================================
    # LAYER 1: CORE MAINTENANCE
    # =========================================================================
    def rebuild_core(self, game_state):
        """Rebuild any destroyed core units. Non-negotiable priority."""
        # Rebuild supports first (they buff turrets)
        for loc in self.core_supports:
            if not game_state.contains_stationary_unit(loc):
                game_state.attempt_spawn(SUPPORT, loc)
                game_state.attempt_upgrade(loc)
        
        # Rebuild turrets
        for loc in self.core_turrets:
            if not game_state.contains_stationary_unit(loc):
                game_state.attempt_spawn(TURRET, loc)
    
    # =========================================================================
    # LAYER 2: OPENING SCRIPT (Rounds 1-3)
    # =========================================================================
    def round_1_defense(self, game_state):
        """Round 1: Build core base and upgrade 3 supports."""
        # Place all 4 supports
        for loc in self.core_supports:
            game_state.attempt_spawn(SUPPORT, loc)
        
        # Place all 4 turrets
        for loc in self.core_turrets:
            game_state.attempt_spawn(TURRET, loc)
        
        # Upgrade first 3 supports: [13,8], [14,8], [13,7]
        upgrades_to_do = [[13, 8], [14, 8], [13, 7]]
        for loc in upgrades_to_do:
            game_state.attempt_upgrade(loc)
    
    def round_2_defense(self, game_state, current_attack):
        """Round 2: Upgrade final support, react to Round 1 attack."""
        # Upgrade the final support [14,7]
        game_state.attempt_upgrade([14, 7])
        
        # React to where opponent attacked in Round 1
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
    
    # =========================================================================
    # LAYER 3: PREDICTIVE ENGINE (Round 4+)
    # =========================================================================
    def predictive_defense(self, game_state, current_attack):
        """Predict opponent's next attack based on pattern matching."""
        # Update history with last attack
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
        """Convert location to zone identifier (left/right/center)."""
        x = location[0]
        if x < 10:
            return 'left'
        elif x > 17:
            return 'right'
        else:
            return 'center'
    
    def predict_attack_zone(self, game_state):
        """Pattern match against behavioral archetypes."""
        if len(self.attack_history) < 3:
            # Not enough data, use simulation fallback
            return self.find_weakest_lane(game_state)
        
        A, B, C = self.attack_history[-3], self.attack_history[-2], self.attack_history[-1]
        
        # Spammer: A → A → A (same zone 3 times)
        if A == B == C:
            return self.zone_to_representative_location(A)
        
        # Alternator: A → B → A (ping-pong)
        if A == C and A != B:
            return self.zone_to_representative_location(B)
        
        # Switch-Up: A → A → B (feint)
        if A == B and B != C:
            return self.zone_to_representative_location(A)
        
        # No pattern match - use simulation fallback
        return self.find_weakest_lane(game_state)
    
    def zone_to_representative_location(self, zone):
        """Convert zone to a representative location for defense."""
        if zone == 'left':
            return [3, 12]
        elif zone == 'right':
            return [24, 12]
        else:
            return [13, 0]
    
    def find_weakest_lane(self, game_state):
        """Simulate paths from enemy spawns to find weakest defense."""
        # Enemy spawn points (top edge)
        enemy_spawns = [[13, 27], [14, 27], [0, 14], [27, 14], [6, 21], [21, 21]]
        
        min_damage = float('inf')
        weakest_spawn = None
        
        for spawn in enemy_spawns:
            path = game_state.find_path_to_edge(spawn)
            if path is None:
                continue
            
            damage = 0
            for loc in path:
                attackers = game_state.get_attackers(loc, 0)
                damage += len(attackers) * self.cached_turret_damage
            
            if damage < min_damage:
                min_damage = damage
                weakest_spawn = spawn
        
        # Return the endpoint in our territory
        if weakest_spawn:
            path = game_state.find_path_to_edge(weakest_spawn)
            if path:
                # Find the deepest point in our territory (y <= 13)
                for loc in reversed(path):
                    if loc[1] <= 13:
                        return loc
        
        return [13, 0]  # Default fallback
    
    # =========================================================================
    # LAYER 4: WALL/PATH DEFENSE SYSTEM
    # =========================================================================
    def wall_path_defense(self, game_state, target_location):
        """Three-phase surgical turret placement along attack path."""
        # Get the path from target to our edge
        path = game_state.find_path_to_edge(target_location)
        if not path:
            self.afk_fallback(game_state)
            return
        
        # Filter path to only our territory (y <= 13)
        our_path = [loc for loc in path if loc[1] <= 13]
        if not our_path:
            self.afk_fallback(game_state)
            return
        
        turrets_placed = 0
        sp_cost = game_state.type_cost(TURRET)[SP]
        
        # Phase 1: Place 1 turret at absolute edge (end of path)
        edge_loc = our_path[-1] if our_path else None
        if edge_loc:
            adjacent = self.get_adjacent_cells(edge_loc, game_state)
            for loc in adjacent:
                if turrets_placed >= 1:
                    break
                if game_state.get_resource(SP) >= sp_cost and not game_state.contains_stationary_unit(loc):
                    if game_state.attempt_spawn(TURRET, loc):
                        turrets_placed += 1
        
        # Phase 2: Place 2 turrets at choke point (1 step from edge)
        if len(our_path) >= 2:
            choke_loc = our_path[-2]
            adjacent = self.get_adjacent_cells(choke_loc, game_state)
            for loc in adjacent:
                if turrets_placed >= 3:
                    break
                if game_state.get_resource(SP) >= sp_cost and not game_state.contains_stationary_unit(loc):
                    if game_state.attempt_spawn(TURRET, loc):
                        turrets_placed += 1
        
        # Phase 3: SP Dump - walk backwards up the path
        for i in range(len(our_path) - 3, -1, -1):
            if game_state.get_resource(SP) < sp_cost:
                break
            
            path_loc = our_path[i]
            # Try path cell and adjacent cells
            candidates = [path_loc] + self.get_adjacent_cells(path_loc, game_state)
            
            for loc in candidates:
                if game_state.get_resource(SP) < sp_cost:
                    break
                if not game_state.contains_stationary_unit(loc):
                    game_state.attempt_spawn(TURRET, loc)
    
    def get_adjacent_cells(self, location, game_state):
        """Get valid adjacent cells in our territory."""
        x, y = location
        candidates = [[x+1, y], [x-1, y], [x, y+1], [x, y-1]]
        valid = []
        for loc in candidates:
            if loc[1] <= 13 and game_state.game_map.in_arena_bounds(loc):
                valid.append(loc)
        return valid
    
    # =========================================================================
    # LAYER 5: AFK FALLBACK
    # =========================================================================
    def afk_fallback(self, game_state):
        """If no attacks, ring turrets around core supports."""
        sp_cost = game_state.type_cost(TURRET)[SP]
        
        # Expand outward from core supports
        for radius in range(1, 6):
            for support_loc in self.core_supports:
                sx, sy = support_loc
                for dx in range(-radius, radius + 1):
                    dy_vals = [radius - abs(dx), -(radius - abs(dx))] if radius != abs(dx) else [0]
                    for dy in dy_vals:
                        loc = [sx + dx, sy + dy]
                        if game_state.get_resource(SP) < sp_cost:
                            return
                        if loc[1] <= 13 and game_state.game_map.in_arena_bounds(loc):
                            if not game_state.contains_stationary_unit(loc):
                                game_state.attempt_spawn(TURRET, loc)
    
    # =========================================================================
    # OFFENSE: PHASES 1-4
    # =========================================================================
    def round_1_offense(self, game_state):
        """Round 1: Deploy 5 Scouts from [13,0], seed ban system."""
        game_state.attempt_spawn(SCOUT, [13, 0], 5)
        self.last_launchpad = [13, 0]
    
    def execute_offense(self, game_state):
        """Round 2+: Ban system + simulation + maximum swarm."""
        if game_state.get_resource(MP) < 1:
            return
        
        # Phase 2: Memory Ban System - remove last used launchpad
        candidates = [lp for lp in self.all_launchpads if lp != self.last_launchpad]
        
        # Phase 3: Fast-Math Simulation - find safest route
        best_launchpad = self.find_safest_launchpad(game_state, candidates)
        
        # Phase 4: Maximum Swarm - all MP into Scouts
        mp_available = int(game_state.get_resource(MP))
        game_state.attempt_spawn(SCOUT, best_launchpad, mp_available)
        
        # Store for next round's ban
        self.last_launchpad = best_launchpad
    
    def find_safest_launchpad(self, game_state, candidates):
        """Score each launchpad by damage and return safest."""
        best_score = float('inf')
        best_launchpad = candidates[0] if candidates else [13, 0]
        
        for launchpad in candidates:
            path = game_state.find_path_to_edge(launchpad)
            if path is None:
                continue
            
            damage_score = 0
            for loc in path:
                # Count enemy turrets in range (squared distance <= 6.25)
                attackers = game_state.get_attackers(loc, 0)
                damage_score += len(attackers) * self.cached_turret_damage
            
            if damage_score < best_score:
                best_score = damage_score
                best_launchpad = launchpad
        
        return best_launchpad

    # =========================================================================
    # ACTION FRAME HANDLER - Track enemy attacks
    # =========================================================================
    def on_action_frame(self, turn_string):
        """Track where enemy units breach or penetrate deepest."""
        state = json.loads(turn_string)
        events = state.get("events", {})
        
        # Track breaches (enemy units scoring on us)
        for breach in events.get("breach", []):
            if len(breach) >= 4:
                loc = breach[0]
                # Enemy breach means location is in our territory (y <= 13)
                if loc[1] <= 13:
                    self.last_attack_location = loc
        
        # Also track enemy unit movement to find deepest penetration
        for move in events.get("move", []):
            if len(move) >= 4:
                loc = move[0]
                owner = move[3] if len(move) > 3 else None
                # Owner 2 is enemy
                if owner == 2 and loc[1] <= 13:
                    # Track the deepest point (lowest y in our territory)
                    if self.last_attack_location is None or loc[1] < self.last_attack_location[1]:
                        self.last_attack_location = loc

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
