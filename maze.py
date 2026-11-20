"""Editable maze data. No files, terminal output, or graphics are used here."""


class MazeError(ValueError):
    """A maze has invalid data or cannot yet be solved/saved."""


class Maze:
    """A rectangular grid; editing is allowed to leave its endpoints incomplete."""

    SYMBOLS = {"#", " ", "S", "E"}
    DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))

    def __init__(self, rows):
        rows = list(rows)
        if not rows or not all(isinstance(row, str) for row in rows):
            raise MazeError("The maze must contain text rows.")
        if not rows[0]:
            raise MazeError("The maze must have at least one column.")
        width = len(rows[0])
        self._markers = {"S": set(), "E": set()}
        for r, row in enumerate(rows):
            if len(row) != width:
                raise MazeError(f"Row {r + 1} has {len(row)} columns; expected {width}.")
            for c, symbol in enumerate(row):
                if symbol not in self.SYMBOLS:
                    raise MazeError(f"Invalid character {symbol!r} at row {r + 1}, column {c + 1}.")
                if symbol in self._markers:
                    self._markers[symbol].add((r, c))
        self._rows = [list(row) for row in rows]
        self.height, self.width = len(rows), width

    @classmethod
    def blank(cls, width, height):
        """Make a corridor grid, with a border when both dimensions allow it."""
        if type(width) is not int or type(height) is not int or min(width, height) < 1:
            raise MazeError("Width and height must be positive integers.")
        rows = [[" " for _ in range(width)] for _ in range(height)]
        if min(width, height) >= 3:
            for r in range(height):
                for c in range(width):
                    if r in (0, height - 1) or c in (0, width - 1):
                        rows[r][c] = "#"
        cells = [(r, c) for r in range(height) for c in range(width) if rows[r][c] == " "]
        rows[cells[0][0]][cells[0][1]] = "S"
        if len(cells) > 1:
            rows[cells[-1][0]][cells[-1][1]] = "E"
        return cls("".join(row) for row in rows)

    @property
    def start(self):
        return next(iter(self._markers["S"])) if len(self._markers["S"]) == 1 else None

    @property
    def end(self):
        return next(iter(self._markers["E"])) if len(self._markers["E"]) == 1 else None

    def issues(self):
        return [f"Place exactly one {symbol} (currently {len(cells)})."
                for symbol, cells in self._markers.items() if len(cells) != 1]

    def validate(self):
        issues = self.issues()
        if issues:
            raise MazeError(" ".join(issues))

    def snapshot(self):
        """Immutable rows: safe for undo, dirty tracking, and independent solvers."""
        return tuple("".join(row) for row in self._rows)

    def copy(self):
        return Maze(self.snapshot())

    def contains(self, cell):
        r, c = cell
        return 0 <= r < self.height and 0 <= c < self.width

    def cell(self, position):
        if not self.contains(position):
            raise IndexError("Cell is outside the maze.")
        return self._rows[position[0]][position[1]]

    def walkable(self, position):
        return self.contains(position) and self.cell(position) != "#"

    def neighbours(self, position):
        r, c = position
        return [(r + dr, c + dc) for dr, dc in self.DIRECTIONS
                if self.walkable((r + dr, c + dc))]

    def _write(self, position, symbol):
        r, c = position
        old = self._rows[r][c]
        if old == symbol:
            return False
        if old in self._markers:
            self._markers[old].discard(position)
        self._rows[r][c] = symbol
        if symbol in self._markers:
            self._markers[symbol].add(position)
        return True

    def set_cell(self, position, symbol):
        """Move unique markers automatically; painting over one can remove it."""
        if symbol not in self.SYMBOLS:
            raise MazeError("Choose a wall, corridor, start, or exit.")
        if not self.contains(position):
            return False
        changed = False
        if symbol in self._markers:
            for old in list(self._markers[symbol]):
                if old != position:
                    changed = self._write(old, " ") or changed
        return self._write(position, symbol) or changed
