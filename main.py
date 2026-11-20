"""Launch the Pygame application, or solve a maze as ASCII without Pygame."""

import argparse
from pathlib import Path

from maze import MazeError
from maze_io import load_maze, solution_text
from solver import MazeSolver


def main():
    parser = argparse.ArgumentParser(description="PyMaze: animated BFS and maze editor")
    parser.add_argument("maze", nargs="?", type=Path, help="ASCII maze to open")
    parser.add_argument("--ascii", action="store_true", help="solve in the terminal; no graphics required")
    parser.add_argument("--fullscreen", action="store_true", help="start fullscreen (F11 toggles)")
    args = parser.parse_args()
    path = args.maze or Path(__file__).resolve().parent / "mazes" / "05_demo.txt"
    if args.ascii:
        try:
            maze = load_maze(path)
            route = MazeSolver(maze).solve()
        except (MazeError, OSError) as error:
            parser.exit(1, f"Could not open maze: {error}\n")
        print(solution_text(maze, None))
        if route is None:
            print("No route exists.")
        else:
            print()
            print(solution_text(maze, route))
            print(f"Shortest route: {len(route) - 1} moves")
    else:
        try:
            from app import MazeApp
        except ModuleNotFoundError as error:
            if error.name != "pygame":
                raise
            parser.exit(1, "Install Pygame first: python -m pip install -r requirements.txt\n")
        MazeApp(path, fullscreen=args.fullscreen).run()


if __name__ == "__main__":
    main()
