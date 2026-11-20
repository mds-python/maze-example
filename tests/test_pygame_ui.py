"""Exercise real Pygame events and dialogs with SDL's offscreen video driver."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from pathlib import Path
import tempfile
import unittest
import pygame

from app import MazeApp
from maze import Maze
from maze_io import load_maze, parse_maze
from ui_widgets import ConfirmDialog, FileDialog, FormDialog, MessageDialog, wrapped

ROOT = Path(__file__).resolve().parents[1]


def key(value, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=value, mod=mod, unicode="")


def click(position, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=position, button=button)


class PygameWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = MazeApp(ROOT / "mazes/03_cycle.txt")
        self.app.frame([], 0)

    def tearDown(self):
        pygame.quit()

    def frame(self, *events, seconds=0):
        self.app.frame(events, seconds)

    def test_solve_pause_step_finish_and_replay(self):
        self.frame(key(pygame.K_RETURN))
        self.assertFalse(self.app.playback.paused)
        self.frame(seconds=0.1)
        self.assertGreater(len(self.app.playback.solver.processed), 0)
        self.frame(key(pygame.K_SPACE))
        processed = len(self.app.playback.solver.processed)
        self.frame(seconds=0.1)
        self.assertEqual(len(self.app.playback.solver.processed), processed)
        self.frame(key(pygame.K_PERIOD))
        self.assertEqual(len(self.app.playback.solver.processed), processed + 1)
        self.frame(key(pygame.K_SPACE))
        for _ in range(100):
            self.frame(seconds=0.1)
            if self.app.playback.finished:
                break
        self.assertEqual(self.app.playback.phase, "complete")
        self.assertEqual(len(self.app.playback.revealed_path) - 1, 18)
        self.frame(key(pygame.K_RETURN))
        self.assertEqual(self.app.playback.revealed_path, [])
        self.frame(key(pygame.K_r))
        self.assertIsNone(self.app.playback)

    def test_paint_drag_undo_redo_and_marker_move(self):
        before = self.app.maze.snapshot()
        self.frame(key(pygame.K_RETURN), key(pygame.K_2))
        self.assertTrue(self.app.editing)
        first = self.app.view.center((0, 1))
        last = self.app.view.center((0, 4))
        self.frame(click(first), pygame.event.Event(pygame.MOUSEMOTION, pos=last,
            rel=(last[0]-first[0], last[1]-first[1]), buttons=(1, 0, 0)),
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=last, button=1))
        self.assertIsNone(self.app.playback)
        self.assertEqual(self.app.maze.snapshot()[0][1:5], "    ")
        self.assertTrue(self.app.dirty)
        self.assertEqual(len(self.app.undo_stack), 1)
        self.frame(key(pygame.K_z, pygame.KMOD_CTRL))
        self.assertEqual(self.app.maze.snapshot(), before)
        self.assertFalse(self.app.dirty)
        self.frame(key(pygame.K_y, pygame.KMOD_CTRL))
        self.assertEqual(self.app.maze.snapshot()[0][1:5], "    ")
        self.frame(key(pygame.K_3))
        position = self.app.view.center((0, 2))
        self.frame(click(position), pygame.event.Event(pygame.MOUSEBUTTONUP, pos=position, button=1))
        self.assertEqual(self.app.maze.start, (0, 2))
        self.assertEqual(sum(row.count("S") for row in self.app.maze.snapshot()), 1)

    def test_open_browser_keyboard_and_invalid_file_preserves_state(self):
        self.frame(key(pygame.K_o, pygame.KMOD_CTRL))
        self.assertIsInstance(self.app.modal, FileDialog)
        self.frame(pygame.event.Event(pygame.TEXTINPUT, text=str(ROOT / "mazes/01_simple.txt")),
                   key(pygame.K_RETURN))
        self.assertIsNone(self.app.modal)
        self.assertEqual(self.app.maze.width, 9)
        before = self.app.maze.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "bad.txt"
            invalid.write_text("S E\n#\n")
            self.app.load_file(invalid)
            self.assertIsInstance(self.app.modal, MessageDialog)
            self.assertEqual(self.app.maze.snapshot(), before)

    def test_save_browser_and_overwrite_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "saved.txt"
            long_path = str(target) * 12
            lines = wrapped(self.app.fonts["normal"], long_path, 320)
            self.assertTrue(all(self.app.fonts["normal"].size(line)[0] <= 320 for line in lines))
            self.frame(key(pygame.K_s, pygame.KMOD_CTRL | pygame.KMOD_SHIFT))
            self.assertIsInstance(self.app.modal, FileDialog)
            self.frame(pygame.event.Event(pygame.TEXTINPUT, text=str(target)), key(pygame.K_RETURN))
            self.assertTrue(target.is_file())
            self.assertFalse(self.app.dirty)
            original = target.read_bytes()
            self.app.maze.set_cell((0, 0), " ")
            self.app.after_edit()
            self.frame(key(pygame.K_s, pygame.KMOD_CTRL))
            self.assertIsInstance(self.app.modal, ConfirmDialog)
            self.frame(key(pygame.K_RETURN))  # Enter cancels replacement.
            self.assertEqual(target.read_bytes(), original)
            self.assertTrue(self.app.dirty)
            self.frame(key(pygame.K_s, pygame.KMOD_CTRL), key(pygame.K_y))
            self.assertFalse(self.app.dirty)
            self.assertEqual(load_maze(target).snapshot(), self.app.maze.snapshot())
            self.assertNotIn(b"*", target.read_bytes())

    def test_new_dimensions_and_tiny_grid(self):
        self.frame(key(pygame.K_n, pygame.KMOD_CTRL))
        self.assertIsInstance(self.app.modal, FormDialog)
        self.frame(pygame.event.Event(pygame.TEXTINPUT, text="1"), key(pygame.K_TAB),
                   pygame.event.Event(pygame.TEXTINPUT, text="5"), key(pygame.K_RETURN))
        self.assertIsNone(self.app.modal)
        self.assertEqual((self.app.maze.width, self.app.maze.height), (1, 5))
        self.app.maze.validate()
        self.assertTrue(self.app.editing)
        self.frame()

    def test_bad_dimensions_leave_form_open(self):
        before = self.app.maze.snapshot()
        self.frame(key(pygame.K_n, pygame.KMOD_CTRL))
        self.frame(pygame.event.Event(pygame.TEXTINPUT, text="0"), key(pygame.K_RETURN))
        self.assertIsInstance(self.app.modal, FormDialog)
        self.assertTrue(self.app.modal.error)
        self.assertEqual(self.app.maze.snapshot(), before)

    def test_file_browser_mouse_selection_and_open(self):
        self.frame(click(self.app.buttons["open"].rect.center))
        dialog = self.app.modal
        self.assertIsInstance(dialog, FileDialog)
        index = next(i for i, path in enumerate(dialog.entries) if path.name == "01_simple.txt")
        position = (dialog.list_rect.x + 80,
                    dialog.list_rect.y + index * dialog.ROW_HEIGHT + 12)
        self.frame(click(position), click(dialog.buttons[-1].rect.center))
        self.assertIsNone(self.app.modal)
        self.assertEqual(self.app.maze.width, 9)

    def test_no_route_display_and_complete_step_is_inert(self):
        self.app.load_file(ROOT / "mazes/04_no_solution.txt")
        self.frame(key(pygame.K_RETURN))
        for _ in range(50):
            self.frame(seconds=0.1)
            if self.app.playback.finished:
                break
        self.assertEqual(self.app.playback.phase, "unreachable")
        previous = self.app.playback
        self.frame(key(pygame.K_PERIOD))
        self.assertIs(self.app.playback, previous)

    def test_focus_loss_commits_stroke_and_pauses(self):
        self.frame(key(pygame.K_2))
        cell = self.app.view.center((0, 1))
        self.frame(click(cell), pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertIsNone(self.app.paint_button)
        self.assertEqual(len(self.app.undo_stack), 1)

    def test_failed_save_keeps_dirty_state(self):
        self.app.maze.set_cell((0, 0), " ")
        self.app.after_edit()
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing" / "maze.txt"
            self.assertFalse(self.app.write_file(missing))
        self.assertTrue(self.app.dirty)
        self.assertIsInstance(self.app.modal, MessageDialog)

    def test_incomplete_maze_blocks_save_and_solve(self):
        self.app.maze.set_cell(self.app.maze.end, " ")
        self.app.after_edit()
        self.frame(key(pygame.K_RETURN))
        self.assertIsInstance(self.app.modal, MessageDialog)
        self.assertIsNone(self.app.playback)
        self.frame(key(pygame.K_RETURN), key(pygame.K_s, pygame.KMOD_CTRL))
        self.assertIsInstance(self.app.modal, MessageDialog)

    def test_quit_requires_discard_for_dirty_maze(self):
        self.app.maze.set_cell((0, 0), " ")
        self.app.after_edit()
        self.frame(pygame.event.Event(pygame.QUIT))
        self.assertTrue(self.app.running)
        self.assertIsInstance(self.app.modal, ConfirmDialog)
        self.frame(key(pygame.K_ESCAPE))
        self.assertTrue(self.app.running)
        self.frame(pygame.event.Event(pygame.QUIT), key(pygame.K_y))
        self.assertFalse(self.app.running)

    def test_large_viewport_can_reach_last_cell(self):
        self.app.replace_maze(Maze.blank(200, 150), editing=True)
        view = self.app.view
        view.zoom(32, view.rect.center, self.app.maze)
        view.pan(-100000, -100000, self.app.maze)
        point = (view.rect.right - view.cell_size // 2, view.rect.bottom - view.cell_size // 2)
        self.assertEqual(view.cell_at(point, self.app.maze), (149, 199))
        self.frame()


if __name__ == "__main__":
    unittest.main()
