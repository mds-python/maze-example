"""ASCII maze parsing and file operations; no UI or drawing dependencies."""

import os
from pathlib import Path
import tempfile

from maze import Maze, MazeError


def parse_maze(text):
    if not isinstance(text, str):
        raise MazeError("Expected maze text.")
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        raise MazeError("Use LF or CRLF line endings.")
    rows = text.split("\n")
    if rows and rows[-1] == "":
        rows.pop()  # One optional final newline, never corridor spaces.
    maze = Maze(rows)
    maze.validate()
    return maze


def load_maze(path):
    try:
        with Path(path).expanduser().open("r", encoding="ascii", newline="") as source:
            return parse_maze(source.read())
    except UnicodeError as error:
        raise MazeError("Maze files must contain ASCII: #, spaces, S, and E.") from error


def maze_text(maze):
    maze.validate()
    return "\n".join(maze.snapshot()) + "\n"


def save_maze(maze, path, overwrite=False):
    """Validate before writing; replacing an existing file requires explicit opt-in."""
    text = maze_text(maze)
    path = Path(path).expanduser()
    if not overwrite:
        with path.open("x", encoding="ascii", newline="\n") as target:
            target.write(text)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="ascii", newline="\n",
                                         dir=path.parent, delete=False) as target:
            temporary = Path(target.name)
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def solution_text(maze, path):
    rows = [list(row) for row in maze.snapshot()]
    if path:
        for r, c in path:
            if rows[r][c] == " ":
                rows[r][c] = "*"
    return "\n".join("".join(row) for row in rows)
