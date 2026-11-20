"""Pygame application controller: interaction, editor history, and file dialogs.

The scaled window, clipped tile board, bitmap HUD, event-loop controls, and
sprite atlas are based on Maciej Dems' PyRobbo (2019), GPL-3.0-or-later.
Maze/search state is deliberately kept outside this graphics module.
"""

from pathlib import Path
import pygame

from maze import Maze, MazeError
from maze_io import load_maze, save_maze
from playback import Playback
from ui_widgets import (SCREEN_SIZE, BG, PANEL, TEXT, MUTED, ACCENT, GOLD, RED,
                        Button, ConfirmDialog, FileDialog, FormDialog, MessageDialog,
                        label, panel)
from view import SpriteAtlas, MazeView, PROCESSED, FRONTIER


class MazeApp:
    HISTORY_LIMIT = 100

    def __init__(self, path=None, fullscreen=False):
        pygame.display.init()
        pygame.font.init()
        self.dummy = pygame.display.get_driver() == "dummy"
        # Same logical-window approach as PyRobbo; SDL maps mouse coordinates.
        self.window_flags = 0 if self.dummy else pygame.SCALED | pygame.RESIZABLE
        self.fullscreen = bool(fullscreen and not self.dummy)
        flags = self.window_flags | (pygame.FULLSCREEN if self.fullscreen else 0)
        self.screen = pygame.display.set_mode(SCREEN_SIZE, flags)
        pygame.display.set_caption("PyMaze — search & editor")
        pygame.key.set_repeat(350, 45)
        pygame.key.start_text_input()
        self.clock = pygame.time.Clock()
        self.fonts = {"title": pygame.font.Font(None, 46),
                      "heading": pygame.font.Font(None, 32),
                      "normal": pygame.font.Font(None, 25),
                      "small": pygame.font.Font(None, 21)}
        self.atlas = SpriteAtlas()
        pygame.display.set_icon(self.atlas.icon(52))
        self.view = MazeView((296, 112, 960, 592), self.atlas)
        self.running, self.modal = True, None
        self.speed, self.playback = 80, None
        self.editing, self.tool = False, "#"
        self.undo_stack, self.redo_stack = [], []
        self.stroke_before, self.paint_button, self.last_cell = None, None, None
        self.panning = False
        self.file_path, self.dirty = None, False
        self.status = "Enter / Solve starts the search. E switches to the editor."
        self.status_colour = MUTED
        error = None
        try:
            self.maze = load_maze(path) if path is not None else Maze.blank(25, 17)
            self.file_path = Path(path).expanduser().resolve() if path is not None else None
        except (MazeError, OSError, ValueError) as caught:
            self.maze, error = Maze.blank(25, 17), caught
        self.saved_snapshot = self.maze.snapshot()
        self.view.fit(self.maze)
        self.buttons = self.make_buttons()
        if error is not None:
            self.show_message("Could not open maze", str(error))

    def make_buttons(self):
        specs = [
            ("new", (28, 136, 68, 34), "New"),
            ("open", (104, 136, 68, 34), "Open"),
            ("save", (180, 136, 68, 34), "Save"),
            ("solve", (28, 216, 220, 42), "SOLVE  [Enter]"),
            ("pause", (28, 270, 104, 34), "Play / pause"),
            ("step", (144, 270, 104, 34), "Step  [.]"),
            ("reset", (28, 312, 104, 32), "Reset  [R]"),
            ("fit", (144, 312, 104, 32), "Fit  [F]"),
            ("slower", (28, 388, 46, 32), "−"),
            ("faster", (202, 388, 46, 32), "+"),
            ("edit", (28, 450, 220, 36), "EDITOR OFF  [E]"),
            ("wall", (28, 530, 104, 34), "1  Wall"),
            ("floor", (144, 530, 104, 34), "2  Floor"),
            ("start", (28, 572, 104, 34), "3  Start"),
            ("end", (144, 572, 104, 34), "4  Exit"),
            ("undo", (28, 620, 104, 32), "Undo"),
            ("redo", (144, 620, 104, 32), "Redo"),
            ("zoom_out", (28, 694, 46, 32), "−"),
            ("zoom_in", (202, 694, 46, 32), "+"),
        ]
        return {key: Button(rect, text, key, primary=key == "solve") for key, rect, text in specs}

    def say(self, message, colour=MUTED):
        self.status, self.status_colour = message, colour

    def open_modal(self, modal):
        self.finish_stroke()
        self.panning = False
        if self.playback:
            self.playback.paused = True
            self.playback.credit = 0.0
        self.modal = modal

    def show_message(self, title, message):
        self.open_modal(MessageDialog(title, message))

    def ask_discard(self, action):
        self.finish_stroke()
        if self.dirty:
            self.open_modal(ConfirmDialog("Unsaved maze changes",
                "Your maze has unsaved edits. Discard these edits and continue? "
                "Choose Cancel to keep the current maze; Ctrl+S saves it.",
                action="Discard", on_result=lambda accepted: action() if accepted else None))
        else:
            action()

    def replace_maze(self, maze, path=None, editing=False):
        self.maze = maze
        self.file_path = Path(path).expanduser().resolve() if path is not None else None
        self.saved_snapshot = maze.snapshot() if path is not None else None
        self.dirty = path is None
        self.playback = None
        self.undo_stack, self.redo_stack = [], []
        self.editing = editing
        self.view.fit(maze)
        self.say("New maze: choose a tool and paint." if editing else "Maze loaded. Ready to solve.", ACCENT)

    def request_open(self):
        def choose():
            initial = self.file_path.parent if self.file_path else Path(__file__).resolve().parent / "mazes"
            self.open_modal(FileDialog(initial, on_result=lambda path: self.load_file(path) if path else None))
        self.ask_discard(choose)

    def load_file(self, path):
        try:
            maze = load_maze(path)
        except (MazeError, OSError, ValueError) as error:
            self.show_message("Could not open maze", str(error))
            return False
        self.replace_maze(maze, path)
        return True

    def request_new(self):
        def validate(values):
            try:
                width, height = int(values["Width"]), int(values["Height"])
                if 1 <= width <= 512 and 1 <= height <= 512:
                    return ""
            except ValueError:
                pass
            return "Enter whole numbers from 1 to 512 for width and height."

        def create(values):
            if values:
                maze = Maze.blank(int(values["Width"]), int(values["Height"]))
                self.replace_maze(maze, editing=True)

        def choose():
            self.open_modal(FormDialog("Create a new maze",
                [("Width", self.maze.width), ("Height", self.maze.height)],
                validate=validate, on_result=create))
        self.ask_discard(choose)

    def request_save(self, save_as=False):
        self.finish_stroke()
        try:
            self.maze.validate()
        except MazeError as error:
            self.show_message("Maze is incomplete", str(error))
            return
        if self.file_path is not None and not save_as:
            self.confirm_save(self.file_path)
        else:
            initial = self.file_path or Path.cwd() / "untitled.txt"
            self.open_modal(FileDialog(initial, save=True,
                on_result=lambda path: self.confirm_save(path) if path else None))

    def confirm_save(self, path):
        path = Path(path).expanduser()
        try:
            exists = path.exists()
        except (OSError, ValueError) as error:
            self.show_message("Could not save maze", str(error))
            return
        if exists:
            self.open_modal(ConfirmDialog("Replace existing file?",
                f"{path}\n\nThe existing file will be replaced with the maze only. "
                "Search colours and the solution line are never saved.", action="Replace",
                on_result=lambda accepted: self.write_file(path, overwrite=True) if accepted else None))
        else:
            self.write_file(path)

    def write_file(self, path, overwrite=False):
        try:
            save_maze(self.maze, path, overwrite=overwrite)
        except FileExistsError:
            self.confirm_save(path)  # A file appeared since the browser was opened.
            return False
        except (MazeError, OSError, ValueError) as error:
            self.show_message("Could not save maze", str(error))
            return False
        self.file_path = Path(path).expanduser().resolve()
        self.saved_snapshot = self.maze.snapshot()
        self.dirty = False
        self.say(f"Saved {self.file_path.name}", ACCENT)
        return True

    def start_search(self, paused=False):
        self.finish_stroke()
        try:
            self.playback = Playback(self.maze, self.speed)
        except MazeError as error:
            self.show_message("Maze is incomplete", str(error))
            return False
        self.editing = False
        self.playback.paused = paused
        self.say("BFS explores one cell per step, then draws a shortest route.")
        return True

    def toggle_play(self):
        if self.playback is None or self.playback.finished:
            self.start_search()
        else:
            self.playback.paused = not self.playback.paused

    def single_step(self):
        if self.playback is not None and self.playback.finished:
            return
        if self.playback is None:
            if not self.start_search(paused=True):
                return
        self.playback.single_step()

    def reset_search(self):
        self.playback = None
        self.say("Search cleared; maze edits have been kept. Enter replays the search.")

    def change_speed(self, multiplier):
        self.speed = max(1, min(2000, round(self.speed * multiplier)))
        if self.playback:
            self.playback.speed = self.speed

    def toggle_editor(self):
        self.finish_stroke()
        self.editing = not self.editing
        if self.playback:
            self.playback.paused = True
        self.say("Left-drag paints. Right-drag erases. 1–4 select tools. Ctrl+Z undoes."
                 if self.editing else "Editor off. Enter starts a fresh search.")

    def after_edit(self):
        self.playback = None
        self.dirty = True
        self.say("Maze changed. Old search state has been cleared.", ACCENT)

    def paint(self, cell, symbol):
        if self.maze.set_cell(cell, symbol):
            self.after_edit()

    def paint_line(self, start, end, symbol):
        """Interpolate dragged cells so quick mouse movement leaves no gaps."""
        if start is None:
            self.paint(end, symbol)
            return
        r0, c0 = start
        r1, c1 = end
        distance = max(abs(r1 - r0), abs(c1 - c0))
        for i in range(distance + 1):
            fraction = i / distance if distance else 0
            self.paint((round(r0 + (r1 - r0) * fraction),
                        round(c0 + (c1 - c0) * fraction)), symbol)

    def begin_stroke(self, cell, button):
        self.stroke_before = self.maze.snapshot()
        self.paint_button, self.last_cell = button, cell
        self.paint(cell, " " if button == 3 else self.tool)

    def finish_stroke(self):
        if self.stroke_before is not None:
            after = self.maze.snapshot()
            if self.stroke_before != after:
                self.undo_stack.append(self.stroke_before)
                self.undo_stack = self.undo_stack[-self.HISTORY_LIMIT:]
                self.redo_stack.clear()
            self.dirty = after != self.saved_snapshot
        self.stroke_before, self.paint_button, self.last_cell = None, None, None

    def undo(self):
        self.finish_stroke()
        if self.undo_stack:
            self.redo_stack.append(self.maze.snapshot())
            self.maze = Maze(self.undo_stack.pop())
            self.after_edit()
            self.dirty = self.maze.snapshot() != self.saved_snapshot

    def redo(self):
        self.finish_stroke()
        if self.redo_stack:
            self.undo_stack.append(self.maze.snapshot())
            self.maze = Maze(self.redo_stack.pop())
            self.after_edit()
            self.dirty = self.maze.snapshot() != self.saved_snapshot

    def request_quit(self):
        self.ask_discard(lambda: setattr(self, "running", False))

    def toggle_fullscreen(self):
        if self.dummy:
            return
        self.fullscreen = not self.fullscreen
        flags = pygame.SCALED | pygame.FULLSCREEN if self.fullscreen else self.window_flags
        try:
            self.screen = pygame.display.set_mode(SCREEN_SIZE, flags)
        except pygame.error as error:
            self.fullscreen = False
            self.screen = pygame.display.set_mode(SCREEN_SIZE, self.window_flags)
            self.show_message("Fullscreen unavailable", str(error))

    def help(self):
        message = (
            "Enter: start / replay BFS     Space: play / pause     Period: one step\n"
            "R: clear search only     + / -: change animation speed     F: fit maze\n\n"
            "E: toggle editor     1: walls     2: corridors     3: start S     4: exit E\n"
            "Left-drag: paint     Right-drag: erase     Ctrl+Z / Ctrl+Y: undo / redo\n"
            "Painting S or E moves that marker. Erasing one makes the maze incomplete.\n"
            "Edits clear the old search. A complete maze is required to solve or save.\n\n"
            "Mouse wheel: zoom     Middle-drag or arrow keys: pan     F11: fullscreen\n"
            "Ctrl+N: new     Ctrl+O: open     Ctrl+S: save     Ctrl+Shift+S: save as\n"
            "Ctrl+Q or window close: quit (asks before discarding unsaved edits).\n\n"
            "Gold cells: queued frontier. Blue cells: processed. Mint line: shortest route.\n"
            "Dialogs pause playback. Esc cancels a dialog; file paths can be typed.\n"
            "ASCII files contain # walls, spaces, one S and one E. No border is required."
        )
        dialog = MessageDialog("Controls & maze format", message)
        dialog.rect = pygame.Rect(150, 56, 980, 720)
        dialog.add_buttons([("Close", True)])
        self.open_modal(dialog)

    def action(self, name):
        actions = {"new": self.request_new, "open": self.request_open,
                   "save": self.request_save, "solve": self.start_search,
                   "pause": self.toggle_play, "step": self.single_step,
                   "reset": self.reset_search, "fit": lambda: self.view.fit(self.maze),
                   "slower": lambda: self.change_speed(1 / 1.5),
                   "faster": lambda: self.change_speed(1.5), "edit": self.toggle_editor,
                   "undo": self.undo, "redo": self.redo,
                   "zoom_out": lambda: self.view.zoom(-4, self.view.rect.center, self.maze),
                   "zoom_in": lambda: self.view.zoom(4, self.view.rect.center, self.maze)}
        tools = {"wall": "#", "floor": " ", "start": "S", "end": "E"}
        if name in tools:
            self.tool = tools[name]
            if not self.editing:
                self.toggle_editor()
        elif name in actions:
            actions[name]()

    def handle_key(self, event):
        ctrl = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
        if ctrl:
            commands = {pygame.K_n: self.request_new, pygame.K_o: self.request_open,
                        pygame.K_s: lambda: self.request_save(bool(event.mod & pygame.KMOD_SHIFT)),
                        pygame.K_z: self.undo, pygame.K_y: self.redo, pygame.K_q: self.request_quit}
            if event.key in commands:
                commands[event.key]()
                return
        commands = {pygame.K_RETURN: self.start_search, pygame.K_KP_ENTER: self.start_search,
                    pygame.K_SPACE: self.toggle_play, pygame.K_PERIOD: self.single_step,
                    pygame.K_r: self.reset_search, pygame.K_f: lambda: self.view.fit(self.maze),
                    pygame.K_e: self.toggle_editor, pygame.K_F1: self.help,
                    pygame.K_F11: self.toggle_fullscreen,
                    pygame.K_PLUS: lambda: self.change_speed(1.5),
                    pygame.K_EQUALS: lambda: self.change_speed(1.5),
                    pygame.K_MINUS: lambda: self.change_speed(1 / 1.5)}
        if event.key in commands:
            commands[event.key]()
        elif event.key == pygame.K_ESCAPE:
            self.toggle_editor() if self.editing else self.request_quit()
        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            self.action({pygame.K_1: "wall", pygame.K_2: "floor", pygame.K_3: "start", pygame.K_4: "end"}[event.key])
        else:
            shifts = {pygame.K_LEFT: (32, 0), pygame.K_RIGHT: (-32, 0),
                      pygame.K_UP: (0, 32), pygame.K_DOWN: (0, -32)}
            if event.key in shifts:
                self.view.pan(*shifts[event.key], self.maze)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.request_quit()
            return
        if self.modal is not None:
            dialog = self.modal
            dialog.handle_event(event)
            if dialog.done:
                self.modal = None
                if dialog.on_result:
                    dialog.on_result(dialog.result)
            return
        if event.type == pygame.WINDOWFOCUSLOST:
            self.finish_stroke()
            self.panning = False
            if self.playback:
                self.playback.paused = True
            return
        if event.type == pygame.KEYDOWN:
            self.handle_key(event)
        elif event.type == pygame.MOUSEWHEEL:
            position = pygame.mouse.get_pos()
            if self.view.rect.collidepoint(position):
                self.view.zoom(4 * event.y, position, self.maze)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for button in self.buttons.values():
                    if button.hit(event.pos):
                        self.action(button.value)
                        return
            cell = self.view.cell_at(event.pos, self.maze)
            if event.button == 2 and self.view.rect.collidepoint(event.pos):
                self.finish_stroke()
                self.panning = True
            elif cell is not None and self.editing and event.button in (1, 3):
                self.begin_stroke(cell, event.button)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2:
                self.panning = False
            elif event.button == self.paint_button:
                self.finish_stroke()
        elif event.type == pygame.MOUSEMOTION:
            if self.panning:
                self.view.pan(*event.rel, self.maze)
            elif self.paint_button is not None:
                cell = self.view.cell_at(event.pos, self.maze)
                if cell is not None:
                    symbol = " " if self.paint_button == 3 else self.tool
                    if symbol in ("S", "E"):
                        self.paint(cell, symbol)
                    else:
                        self.paint_line(self.last_cell, cell, symbol)
                    self.last_cell = cell
                else:
                    self.last_cell = None

    def update(self, seconds):
        if self.playback and self.modal is None:
            self.playback.update(seconds)

    def draw(self):
        surface, fonts = self.screen, self.fonts
        surface.fill(BG)
        surface.blit(self.atlas.icon(52, 40), (24, 22))
        label(surface, fonts["title"], "PYMAZE", (78, 20), TEXT)
        label(surface, fonts["small"], "SEARCH  /  BUILD  /  EXPLORE", (266, 36), MUTED)
        label(surface, fonts["small"], "F1  HELP      F11  FULLSCREEN", (991, 36), MUTED)
        pygame.draw.line(surface, (51, 66, 88), (16, 72), (1264, 72))
        panel(surface, (16, 88, 248, 728))
        for text, y in (("WORKSPACE", 106), ("BREADTH-FIRST SEARCH", 190),
                        ("ANIMATION SPEED", 360), ("PAINT TOOLS", 505), ("VIEW / ZOOM", 668)):
            label(surface, fonts["small"], text, (28, y), MUTED)
        self.buttons["edit"].text = "EDITOR ON  [E]" if self.editing else "EDITOR OFF  [E]"
        self.buttons["edit"].selected = self.editing
        self.buttons["undo"].enabled = bool(self.undo_stack)
        self.buttons["redo"].enabled = bool(self.redo_stack)
        self.buttons["pause"].enabled = self.playback is not None and not self.playback.finished
        self.buttons["step"].enabled = self.playback is None or not self.playback.finished
        for name, symbol in (("wall", "#"), ("floor", " "), ("start", "S"), ("end", "E")):
            self.buttons[name].selected = self.editing and self.tool == symbol
        for button in self.buttons.values():
            button.draw(surface, fonts["normal"])
        label(surface, fonts["normal"], f"{self.speed:>4} / sec", (91, 395), GOLD)
        label(surface, fonts["small"], "search cells / route cells", (44, 426), MUTED)
        label(surface, fonts["normal"], f"{self.view.cell_size} px", (105, 701), TEXT)
        for colour, text, y in ((FRONTIER, "Queued frontier", 750),
                                (PROCESSED, "Processed cells", 772),
                                (ACCENT, "Shortest route", 794)):
            pygame.draw.rect(surface, colour, (30, y + 1, 14, 14))
            label(surface, fonts["small"], text, (54, y), MUTED)
        name = self.file_path.name if self.file_path else "Untitled maze"
        name += "  * unsaved" if self.dirty else ""
        label(surface, fonts["small"], name, (296, 86), GOLD if self.dirty else TEXT, 710)
        label(surface, fonts["small"], f"{self.maze.width} × {self.maze.height} cells",
              (1100, 86), MUTED, 156)
        hover = self.view.cell_at(pygame.mouse.get_pos(), self.maze)
        self.view.draw(surface, self.maze, self.playback, fonts, hover, self.editing and not self.modal)
        hint = "Wheel: zoom   |   Middle-drag / arrows: pan   |   F: fit   |   E: editor"
        if hover:
            hint += f"   |   row {hover[0] + 1}, col {hover[1] + 1}"
        label(surface, fonts["small"], hint, (296, 718), MUTED, 960)
        issues = self.maze.issues()
        label(surface, fonts["small"], " ".join(issues) if issues else self.status,
              (296, 740), RED if issues else self.status_colour, 960)
        panel(surface, (280, 766, 984, 50))
        solver = self.playback.solver if self.playback else None
        route = solver.path if solver else None
        for text, value, x in (("PROCESSED", len(solver.processed) if solver else 0, 300),
                               ("FRONTIER", len(solver.frontier) if solver else 0, 500)):
            label(surface, fonts["small"], text, (x, 773), MUTED)
            self.atlas.number(surface, value, (x + 112, 777), places=4, scale=0.75)
        label(surface, fonts["small"], "MOVES", (700, 773), MUTED)
        if route is not None:
            self.atlas.number(surface, len(route) - 1, (780, 777), places=4, scale=0.75)
        else:
            label(surface, fonts["normal"], "----", (780, 781), MUTED)
        phase, colour = "READY", ACCENT
        if issues:
            phase, colour = "INCOMPLETE", RED
        elif self.editing:
            phase, colour = "EDITOR", GOLD
        elif self.playback:
            phase = {"search": "SEARCH", "route": "DRAW ROUTE", "complete": "SOLVED",
                     "unreachable": "NO ROUTE EXISTS"}[self.playback.phase]
            colour = RED if self.playback.phase == "unreachable" else ACCENT
            if self.playback.paused and not self.playback.finished:
                phase += " / PAUSED"
        label(surface, fonts["normal"], phase, (919, 782), colour, 328)
        if self.modal:
            self.modal.draw(surface, fonts)

    def frame(self, events=None, seconds=None):
        """One normal frame; explicit inputs also support deterministic UI checks."""
        if seconds is None:
            seconds = self.clock.tick(60) / 1000
        for event in pygame.event.get() if events is None else events:
            self.handle_event(event)
        self.update(seconds)
        self.draw()
        pygame.display.flip()

    def run(self):
        try:
            while self.running:
                self.frame()
        finally:
            pygame.quit()
