https://py-stockfish.github.io/stockfish/stockfish/models.html

# def update_engine_parameters(self, parameters: dict[str, str | int | bool] | None) -> None:
Updates the Stockfish engine parameters.

parameters

Contains (key, value) pairs which will be used to update the Stockfish engine's current parameters.
Example:

>>> stockfish.update_engine_parameters({'Threads': 2})

# def make_moves_from_start(self, moves: Sequence[str] | None = None) -> None:
Sets the position by making a sequence of moves from the starting position of chess.

moves

A sequence of moves to set this position on the board. Must be in pure algebraic coordinate notation.
Example:

>>> stockfish.make_moves_from_start(['e2e4', 'e7e5'])


# def make_moves_from_current_position(self, moves: Sequence[str] | None) -> None:
Sets a new position by playing the moves from the current position.

moves

A sequence of moves to play in the current position, in order to reach a new position. Must be in pure algebraic coordinate notation.
Example:

>>> stockfish.make_moves_from_current_position(["g4d7", "a8b8", "f1d1"])

# def set_skill_level(self, skill_level: int = 20) -> None:
Sets the skill level of the stockfish engine.

skill_level

Skill Level option between 0 (weakest level) and 20 (full strength).
Example:

>>> stockfish.set_skill_level(10)

# def set_elo_rating(self, elo_rating: int = 1350) -> None:
Sets the elo rating of the Stockfish engine, ignoring skill level.

elo_rating

Gets Stockfish to approximate the strength of the given elo.
Example:

>>> stockfish.set_elo_rating(2500)

# def set_num_nodes(self, num_nodes: int = 1000000) -> None:
Sets the number of nodes for Stockfish to explore during its search.

num_nodes

Number of nodes for Stockfish to search.
Example:

>>> stockfish.set_num_nodes(1000000)

# def get_num_nodes(self) -> int:
Returns the configured number of nodes for Stockfish to search.


# def set_num_nodes(self, num_nodes: int = 1000000) -> None:
Sets the number of nodes for Stockfish to explore during its search.

num_nodes

Number of nodes for Stockfish to search.
Example:

>>> stockfish.set_num_nodes(1000000)

# def get_num_nodes(self) -> int:
Returns the configured number of nodes for Stockfish to search.

# def get_top_moves(
# 	self,
# 	num_top_moves: int = 5,
# 	verbose: bool = False,
# 	num_nodes: int = 0
# ) -> list[dict[str, str | int | None]]:
Returns a list of dictionaries representing the top moves in the position. Each dictionary contains keys for Move, Centipawn, and Mate. The corresponding value for either the Centipawn or Mate key will be None. If there are no moves in the position, an empty list is returned.

If verbose is True, the dictionary will also include the following keys: SelectiveDepth, Time, Nodes, NodesPerSecond, MultiPVNumber, PVMoves, and WDL (if available).

num_top_moves

The number of moves for which to return information, assuming there are at least that many legal moves. Default is 5. Note that this will temporarily replace the engine's current multipv value.
verbose

Option to include the full info from the engine in the returned dictionary, including seldepth, multipv, time, nodes, nps, wdl (if available), and pv. Default is False.
num_nodes

Option to search until a certain number of nodes have been searched, instead of depth. Default is 0.
Example:

>>> stockfish.get_top_moves(2)
[{'Move': 'e2e4', 'Centipawn': 32, 'Mate': None}, {'Move': 'd2d4', 'Centipawn': 31, 'Mate': None}]