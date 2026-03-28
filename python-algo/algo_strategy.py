import gamelib
import random
import math
import warnings
from sys import maxsize
import json


"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

        # Track enemy offensive unit spawn locations accumulated across action frames
        self.current_round_spawns = []
        # History of attack zones ('left'/'right'/None) per completed round
        self.enemy_attack_history = []
        # Whether the enemy has ever spawned offensive units
        self.enemy_spawned_offensive = False

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
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

        # Core positions as specified in the strategy
        self.CORE_SUPPORTS = [[13, 8], [14, 8], [13, 7], [14, 7]]
        self.CORE_TURRETS = [[13, 9], [14, 9], [12, 7], [15, 7]]

        # 6 enemy spawn points spread across top-left and top-right edges
        # used for simulating attacks in the Random/Unknown pattern case
        self.ENEMY_SPAWN_POINTS = [
            [0, 14], [4, 18], [8, 22],    # top-left edge
            [19, 22], [23, 18], [27, 14]  # top-right edge
        ]
        # Centre x-coordinate used to classify attack zones as left or right
        self.ARENA_CENTER_X = 14  # = ARENA_SIZE / 2 = 28 / 2

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)

        # Finalise the previous round's attack zone before making decisions
        zone = self._detect_attack_zone(self.current_round_spawns)
        self.enemy_attack_history.append(zone)
        self.current_round_spawns = []

        self.multi_phase_strategy(game_state)

        game_state.submit_turn()

    # ------------------------------------------------------------------
    # Multi-phase strategy entry point
    # ------------------------------------------------------------------

    def multi_phase_strategy(self, game_state):
        """Dispatch to the correct phase based on the current turn number."""
        turn = game_state.turn_number

        # Phase 1: Core Maintenance (Round 2 onward = turn >= 1)
        if turn >= 1:
            self.maintain_core(game_state)

        # Phase 2 / Opening Script
        if turn == 0:
            self.opening_round_1(game_state)
        elif turn == 1:
            self.opening_round_2(game_state)
        elif turn == 2:
            self.opening_round_3(game_state)
        else:
            # Phase 3: Predictive Engine (Round 4+ = turn >= 3)
            self.predictive_defense(game_state)

    # ------------------------------------------------------------------
    # Phase 1: Core Maintenance
    # ------------------------------------------------------------------

    def maintain_core(self, game_state):
        """Rebuild any destroyed core supports or turrets before anything else."""
        for loc in self.CORE_SUPPORTS:
            if not game_state.contains_stationary_unit(loc):
                game_state.attempt_spawn(SUPPORT, loc)
        for loc in self.CORE_TURRETS:
            if not game_state.contains_stationary_unit(loc):
                game_state.attempt_spawn(TURRET, loc)

    # ------------------------------------------------------------------
    # Phase 2: Opening Script
    # ------------------------------------------------------------------

    def opening_round_1(self, game_state):
        """Round 1 (turn 0): Build core base with initial support upgrades."""
        game_state.attempt_spawn(SUPPORT, self.CORE_SUPPORTS)
        game_state.attempt_spawn(TURRET, self.CORE_TURRETS)
        # Upgrade 3 of the 4 core supports
        game_state.attempt_upgrade([[13, 8], [14, 8], [13, 7]])

    def opening_round_2(self, game_state):
        """Round 2 (turn 1): Upgrade final support, defend Round 1 attack zone."""
        game_state.attempt_upgrade([[14, 7]])
        zone = self.enemy_attack_history[-1] if self.enemy_attack_history else None
        if zone is not None:
            self.wall_path_defense(game_state, zone)
        else:
            self.afk_fallback(game_state)

    def opening_round_3(self, game_state):
        """Round 3 (turn 2): Defend Round 2 attack zone."""
        zone = self.enemy_attack_history[-1] if self.enemy_attack_history else None
        if zone is not None:
            self.wall_path_defense(game_state, zone)
        else:
            self.afk_fallback(game_state)

    # ------------------------------------------------------------------
    # Phase 3: Predictive Engine
    # ------------------------------------------------------------------

    def predictive_defense(self, game_state):
        """Round 4+ (turn 3+): Predict next attack zone from history and defend."""
        if not self.enemy_spawned_offensive:
            self.afk_fallback(game_state)
            return

        history = self.enemy_attack_history
        # Only consider rounds where the enemy actually attacked
        attack_rounds = [z for z in history if z is not None]

        if len(attack_rounds) >= 3:
            a, b, c = attack_rounds[-3], attack_rounds[-2], attack_rounds[-1]
            if a == b == c:
                # The Spammer (A-A-A): defend same spot again
                predicted_zone = c
            elif a == c and a != b:
                # The Alternator (A-B-A): predict they switch back to B
                predicted_zone = b
            elif a == b and b != c:
                # The Switch-Up (A-A-B): assume revert to A
                predicted_zone = a
            else:
                # Random / unknown pattern: simulate weakest path
                predicted_zone = self.find_weakest_path_zone(game_state)
        else:
            predicted_zone = self.find_weakest_path_zone(game_state)

        self.wall_path_defense(game_state, predicted_zone)

    def find_weakest_path_zone(self, game_state):
        """
        Simulate an attack from each of the 6 enemy spawn points, calculate the
        total turret damage along each path, and return the zone ('left'/'right')
        with the least damage (i.e. the weakest / most dangerous path for us).
        """
        turret_damage = gamelib.GameUnit(TURRET, game_state.config).damage_i
        min_damage = float('inf')
        weakest_spawn = self.ENEMY_SPAWN_POINTS[0]

        for spawn in self.ENEMY_SPAWN_POINTS:
            if game_state.contains_stationary_unit(spawn):
                continue
            path = game_state.find_path_to_edge(spawn)
            if not path:
                continue
            damage = sum(
                len(game_state.get_attackers(loc, 0)) * turret_damage
                for loc in path
            )
            if damage < min_damage:
                min_damage = damage
                weakest_spawn = spawn

        return 'left' if weakest_spawn[0] < game_state.HALF_ARENA else 'right'

    # ------------------------------------------------------------------
    # Phase 4: Tactical Placement (Wall / Path Defense)
    # ------------------------------------------------------------------

    def wall_path_defense(self, game_state, zone):
        """
        Defend the given zone using the three-step tactical placement rule:
          1. The Absolute Edge  – 1 turret on the final cell of the enemy path
          2. The Choke Point    – 2 turrets exactly 1 Manhattan step back on path
          3. The SP Dump        – walk backwards up path, drop turrets on path
                                  and adjacent cells until SP = 0
        """
        if zone is None:
            self.afk_fallback(game_state)
            return

        spawn = self._get_spawn_for_zone(zone)

        # If the representative spawn is blocked, try nearby positions
        if game_state.contains_stationary_unit(spawn):
            for dx in range(-3, 4):
                candidate = [spawn[0] + dx, spawn[1]]
                if (game_state.game_map.in_arena_bounds(candidate) and
                        not game_state.contains_stationary_unit(candidate)):
                    spawn = candidate
                    break

        path = game_state.find_path_to_edge(spawn)
        if not path:
            self.afk_fallback(game_state)
            return

        # Keep only the portion of the path that lies in our territory
        our_path = [loc for loc in path if loc[1] < game_state.HALF_ARENA]
        if not our_path:
            self.afk_fallback(game_state)
            return

        turret_cost = game_state.type_cost(TURRET)[SP]

        # --- The Absolute Edge: 1 turret at path end ---
        end_cell = our_path[-1]
        game_state.attempt_spawn(TURRET, end_cell)

        # --- The Choke Point: up to 2 turrets at Manhattan distance 1 from end ---
        choke_placed = 0
        for loc in our_path[:-1]:
            if choke_placed >= 2:
                break
            dist = abs(loc[0] - end_cell[0]) + abs(loc[1] - end_cell[1])
            if dist == 1:
                game_state.attempt_spawn(TURRET, loc)
                choke_placed += 1

        # --- The SP Dump: walk backwards up the path, place turrets until SP=0 ---
        for loc in reversed(our_path):
            if game_state.get_resource(SP) < turret_cost:
                break
            # Place directly on the path cell
            if not game_state.contains_stationary_unit(loc):
                game_state.attempt_spawn(TURRET, loc)
            # Place on immediately adjacent cells
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                adj = [loc[0] + dx, loc[1] + dy]
                if (game_state.game_map.in_arena_bounds(adj) and
                        adj[1] < game_state.HALF_ARENA and
                        not game_state.contains_stationary_unit(adj) and
                        game_state.get_resource(SP) >= turret_cost):
                    game_state.attempt_spawn(TURRET, adj)

    def _get_spawn_for_zone(self, zone):
        """Return a representative enemy spawn location for a given zone."""
        if zone == 'left':
            return [4, 18]   # top-left edge
        else:
            return [23, 18]  # top-right edge

    # ------------------------------------------------------------------
    # Phase 5: AFK Fallback
    # ------------------------------------------------------------------

    def afk_fallback(self, game_state):
        """
        Opponent has never sent offensive units – wrap core supports in a
        protective layer of turrets instead of doing path defense.
        """
        turret_cost = game_state.type_cost(TURRET)[SP]
        core_set = set(map(tuple, self.CORE_SUPPORTS + self.CORE_TURRETS))
        seen = set()

        for support in self.CORE_SUPPORTS:
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                pos = [support[0] + dx, support[1] + dy]
                pos_t = tuple(pos)
                if pos_t in seen or pos_t in core_set:
                    continue
                seen.add(pos_t)
                if (game_state.game_map.in_arena_bounds(pos) and
                        pos[1] < game_state.HALF_ARENA and
                        not game_state.contains_stationary_unit(pos) and
                        game_state.get_resource(SP) >= turret_cost):
                    game_state.attempt_spawn(TURRET, pos)

    # ------------------------------------------------------------------
    # Attack-zone tracking helpers
    # ------------------------------------------------------------------

    def _detect_attack_zone(self, spawns):
        """
        Classify a list of enemy offensive spawn locations as 'left', 'right',
        or None (if no spawns occurred this round).
        """
        if not spawns:
            return None
        avg_x = sum(s[0] for s in spawns) / len(spawns)
        return 'left' if avg_x < self.ARENA_CENTER_X else 'right'

    def on_action_frame(self, turn_string):
        """
        Called for each action frame.  We record the x/y of every offensive
        unit (Scout, Demolisher, Interceptor) spawned by the opponent.

        Full doc on the frame format is in json-docs.html in the root of the
        StarterKit.  In frame events player index 1 = us, 2 = opponent.
        Offensive unit type indices: 3 = Scout, 4 = Demolisher, 5 = Interceptor.
        """
        state = json.loads(turn_string)
        events = state["events"]

        for spawn in events.get("spawn", []):
            # spawn format: [unitTypeInt, x, y, playerIndex, ...]
            if len(spawn) >= 4 and int(spawn[3]) == 2:
                unit_type_idx = int(spawn[0])
                if unit_type_idx in (3, 4, 5):  # Scout, Demolisher, Interceptor
                    self.current_round_spawns.append([int(spawn[1]), int(spawn[2])])
                    self.enemy_spawned_offensive = True


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
