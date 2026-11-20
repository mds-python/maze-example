"""Independent checks of the maze contract, shortest paths, and file safety."""

from pathlib import Path
import tempfile
import unittest

from maze import Maze, MazeError
from maze_io import parse_maze, load_maze, save_maze, solution_text
from solver import MazeSolver
from playback import Playback

ROOT = Path(__file__).resolve().parents[1]


class MazeTests(unittest.TestCase):
    def test_sample_shortest_distances(self):
        for name, expected in (("01_simple.txt", 6), ("02_branches.txt", 16),
                               ("03_cycle.txt", 18), ("04_no_solution.txt", None),
                               ("09_blocked.txt", None)):
            with self.subTest(name=name):
                maze = load_maze(ROOT / "mazes" / name)
                before = maze.snapshot()
                route = MazeSolver(maze).solve()
                if expected is None:
                    self.assertIsNone(route)
                else:
                    self.assertEqual(len(route) - 1, expected)
                    self.assertEqual(route[0], maze.start)
                    self.assertEqual(route[-1], maze.end)
                    self.assertEqual(len(route), len(set(route)))
                    for first, second in zip(route, route[1:]):
                        self.assertEqual(abs(first[0]-second[0])+abs(first[1]-second[1]), 1)
                        self.assertTrue(maze.walkable(second))
                self.assertEqual(before, maze.snapshot())

    def test_one_row_column_and_no_border(self):
        for text, expected in (("SE", 1), ("S  E", 3), ("S\n \nE\n", 2), ("S#E\n   ", 4)):
            with self.subTest(text=text):
                route = MazeSolver(parse_maze(text)).solve()
                self.assertEqual(len(route) - 1, expected)

    def test_spaces_crlf_and_final_newline(self):
        maze = parse_maze(" S E \r\n     \r\n")
        self.assertEqual(maze.snapshot(), (" S E ", "     "))
        self.assertEqual(MazeSolver(maze).solve(), [(0, 1), (0, 2), (0, 3)])
        self.assertEqual(parse_maze(" S E \n     ").snapshot(), maze.snapshot())

    def test_reject_invalid_input(self):
        cases = ["", "\n", "S", "E", "SSE", "SEE", "S. E", "S\tE", "SE\n ",
                 "SE\n\n", "SE\r", "SÉ", "SE\n\n  "]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(MazeError):
                parse_maze(text)

    def test_negative_indices_are_not_neighbours(self):
        maze = parse_maze("S#E")
        self.assertFalse(maze.walkable((0, -1)))
        self.assertEqual(maze.neighbours((0, 0)), [])
        self.assertIsNone(MazeSolver(maze).solve())

    def test_move_and_remove_markers(self):
        maze = parse_maze("S E\n   ")
        maze.set_cell((1, 0), "S")
        self.assertEqual(maze.start, (1, 0))
        self.assertEqual(maze.cell((0, 0)), " ")
        maze.set_cell(maze.end, "#")
        self.assertIsNone(maze.end)
        self.assertTrue(maze.issues())
        with self.assertRaises(MazeError):
            MazeSolver(maze)
        maze.set_cell((1, 2), "E")
        maze.validate()

    def test_solver_retains_independent_input(self):
        maze = parse_maze("S E")
        solver = MazeSolver(maze)
        maze.set_cell((0, 1), "#")
        self.assertEqual(len(solver.solve()), 3)
        self.assertIsNone(MazeSolver(maze).solve())

    def test_save_round_trip_and_explicit_overwrite(self):
        maze = parse_maze(" S E \n     ")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "maze.txt"
            save_maze(maze, target)
            self.assertEqual(load_maze(target).snapshot(), maze.snapshot())
            with self.assertRaises(FileExistsError):
                save_maze(maze, target)
            maze.set_cell((1, 1), "#")
            save_maze(maze, target, overwrite=True)
            self.assertEqual(load_maze(target).snapshot(), maze.snapshot())
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_incomplete_save_does_not_touch_file(self):
        maze = Maze(["S  "])
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "maze.txt"
            target.write_text("SE\n")
            with self.assertRaises(MazeError):
                save_maze(maze, target, overwrite=True)
            self.assertEqual(target.read_text(), "SE\n")
            missing = Path(directory) / "new.txt"
            with self.assertRaises(MazeError):
                save_maze(maze, missing)
            self.assertFalse(missing.exists())

    def test_solution_overlay_preserves_input(self):
        maze = parse_maze("S E")
        self.assertEqual(solution_text(maze, MazeSolver(maze).solve()), "S*E")
        self.assertEqual(maze.snapshot(), ("S E",))


class PlaybackTests(unittest.TestCase):
    def test_search_and_path_reveal_are_separate_steps(self):
        playback = Playback(parse_maze("S E"))
        playback.single_step()
        self.assertTrue(playback.paused)
        self.assertEqual(len(playback.solver.processed), 1)
        self.assertEqual(playback.revealed_path, [])
        playback.single_step()
        playback.single_step()
        self.assertEqual(playback.phase, "route")
        for count in (1, 2, 3):
            playback.single_step()
            self.assertEqual(len(playback.revealed_path), count)
        self.assertEqual(playback.phase, "complete")
        self.assertFalse(playback.advance())

    def test_pause_does_not_accumulate_delayed_steps(self):
        playback = Playback(parse_maze("S   E"), speed=10)
        playback.update(10)
        self.assertEqual(len(playback.solver.processed), 0)
        playback.paused = False
        playback.update(0.1)
        self.assertEqual(len(playback.solver.processed), 1)

    def test_speed_does_not_change_result(self):
        maze = load_maze(ROOT / "mazes/03_cycle.txt")
        results = []
        for speed in (1, 80, 2000):
            playback = Playback(maze, speed)
            playback.paused = False
            for _ in range(10000):
                playback.update(0.1)
                if playback.finished:
                    break
            self.assertTrue(playback.finished)
            results.append(playback.revealed_path)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_unreachable_terminates_and_pauses(self):
        playback = Playback(parse_maze("S#E"))
        playback.advance()
        self.assertEqual(playback.phase, "unreachable")
        self.assertTrue(playback.paused)
        self.assertIsNone(playback.solver.path)


if __name__ == "__main__":
    unittest.main()
