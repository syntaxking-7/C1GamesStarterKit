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
        
        # O(1) Data Structures
        self.our_dead_turrets = []
        self.breach_counts = {}
        self.active_reactive_turrets = set()

    def on_game_start(self, config):
        gamelib.debug_write('Configuring Encryptor-Ramp Reactive Swarm Bot...')
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

        # Fixed Structures
        self.turn_1_turrets = [[12, 8], [13, 8], [14, 8], [15, 8]]
        self.center_supports = [[13, 6], [13, 7], [14, 6], [14, 7]]

    def on_turn(self, turn_state):
        game_state = gamelib.GameState(self.config, turn_state)
        game_state.suppress_warnings(True)

        self.custom_strategy(game_state)
        game_state.submit_turn()

    def custom_strategy(self, game_state):
        # MICRO-OPTIMIZATION: Lazy-load the cache on Turn 1 to bypass
        # the engine's internal circular import bug.
        if not hasattr(self, 'cached_turret_damage'):
            self.cached_turret_damage = gamelib.GameUnit(TURRET, game_state.config).damage_i

        # --- THE ENCRYPTOR RAMP CHECK ---
        supports_maxed = True
        for x, y in self.center_supports:
            unit_found_and_upgraded = False
            for unit in game_state.game_map[x, y]:
                if unit.unit_type == SUPPORT and getattr(unit, 'upgraded', False):
                    unit_found_and_upgraded = True
                    break
            
            if not unit_found_and_upgraded:
                supports_maxed = False
                break

        # --- 1. SP PHASE (BUILD DEFENSES FIRST) ---
        if game_state.turn_number == 0:
            self.build_initial_turrets(game_state)
            self.build_center_supports(game_state)
            
            upgrades_done = 0
            for loc in self.center_supports:
                if upgrades_done < 3 and game_state.contains_stationary_unit(loc):
                    sp_before = game_state.get_resource(SP)
                    game_state.attempt_upgrade([loc])
                    if game_state.get_resource(SP) < sp_before:
                        upgrades_done += 1
            
        elif game_state.turn_number == 1:
            self.build_center_supports(game_state)
            for loc in self.center_supports:
                if game_state.contains_stationary_unit(loc):
                    game_state.attempt_upgrade([loc])
            self.spend_leftover_sp(game_state)
            
        elif game_state.turn_number >= 2:
            self.build_center_supports(game_state)
            self.build_reactive_clusters(game_state)
            self.spend_leftover_sp(game_state)

        # --- 2. MP PHASE (DEPLOY SWARM AFTER MAP IS UPDATED) ---
        if game_state.turn_number == 0:
            if game_state.get_resource(MP) > 0:
                game_state.attempt_spawn(SCOUT, [13, 0], 1000)
                
        elif supports_maxed or game_state.turn_number % 2 != 0:
            self.deploy_swarm(game_state)

    def deploy_swarm(self, game_state):
        if game_state.get_resource(MP) > 0:
            spawn_options = [[13, 0], [14, 0], [2, 11], [25, 11], [7, 6], [20, 6]]
            best_location = self.least_damage_spawn_location(game_state, spawn_options)
            game_state.attempt_spawn(SCOUT, best_location, 1000)

    def build_initial_turrets(self, game_state):
        cost = game_state.type_cost(TURRET)[SP]
        for loc in self.turn_1_turrets:
            if game_state.get_resource(SP) >= cost:
                game_state.attempt_spawn(TURRET, loc)
                self.active_reactive_turrets.add(tuple(loc))

    def build_center_supports(self, game_state):
        cost = game_state.type_cost(SUPPORT)[SP]
        for loc in self.center_supports:
            if not game_state.contains_stationary_unit(loc):
                if game_state.get_resource(SP) >= cost:
                    game_state.attempt_spawn(SUPPORT, loc)

    def build_reactive_clusters(self, game_state):
        if not self.breach_counts:
            return

        most_breached = max(self.breach_counts, key=self.breach_counts.get)
        bx, by = most_breached

        turrets_built = 0
        sp_cost = game_state.type_cost(TURRET)[SP]
        
        for radius in range(0, 10):
            if turrets_built >= 3:
                break
                
            candidates = []
            for dx in range(-radius, radius + 1):
                dy = radius - abs(dx)
                points = [(bx + dx, by + dy), (bx + dx, by - dy)] if dy != 0 else [(bx + dx, by)]
                
                for x, y in points:
                    if y <= 13 and game_state.game_map.in_arena_bounds([x, y]):
                        candidates.append([x, y])
            
            candidates.sort(key=lambda loc: abs(13.5 - loc[0]))

            for loc in candidates:
                if turrets_built >= 3:
                    break
                    
                if not game_state.contains_stationary_unit(loc):
                    if game_state.get_resource(SP) >= sp_cost:
                        sp_before = game_state.get_resource(SP)
                        game_state.attempt_spawn(TURRET, loc)
                        
                        if game_state.get_resource(SP) < sp_before:
                            turrets_built += 1
                            self.active_reactive_turrets.add(tuple(loc))

    def spend_leftover_sp(self, game_state):
        for loc in self.center_supports:
            if game_state.contains_stationary_unit(loc):
                game_state.attempt_upgrade([loc])

    def least_damage_spawn_location(self, game_state, location_options):
        damages = []
        
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            if path is None:
                damages.append(float('inf'))
                continue
            
            damage = 0
            for path_location in path:
                attackers = game_state.get_attackers(path_location, 0)
                damage += len(attackers) * self.cached_turret_damage
            damages.append(damage)
            
        min_damage = min(damages)
        
        if min_damage == float('inf'):
            return random.choice(location_options)
            
        best_locations = [location_options[i] for i, dmg in enumerate(damages) if dmg == min_damage]
        return random.choice(best_locations)

    def on_action_frame(self, turn_string):
        state = json.loads(turn_string)
        events = state.get("events", {})
        
        for death in events.get("death", []):
            if len(death) >= 4:
                loc = death[0]
                if death[1] == TURRET and loc[1] <= 13:
                    self.our_dead_turrets.append(loc)
                    
        for breach in events.get("breach", []):
            if len(breach) >= 4:
                loc = breach[0]
                if loc[1] <= 13:
                    t_loc = tuple(loc)
                    self.breach_counts[t_loc] = self.breach_counts.get(t_loc, 0) + 1

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
