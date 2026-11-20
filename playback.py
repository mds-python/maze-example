"""Animation state and pacing, without any dependence on Pygame."""

from solver import MazeSolver


class Playback:
    def __init__(self, maze, speed=80):
        self.solver = MazeSolver(maze)
        self.phase = "search"
        self.paused = True
        self.speed = speed
        self.revealed_path = []
        self.route_indices = {}
        self.credit = 0.0

    @property
    def finished(self):
        return self.phase in ("complete", "unreachable")

    def advance(self):
        """Perform precisely one search expansion or one route-reveal step."""
        if self.finished:
            return False
        if self.phase == "search":
            self.solver.step()
            if self.solver.finished:
                if self.solver.path is None:
                    self.phase = "unreachable"
                    self.paused = True
                else:
                    self.phase = "route"
        elif self.phase == "route":
            index = len(self.revealed_path)
            cell = self.solver.path[index]
            self.route_indices[cell] = index
            self.revealed_path.append(cell)
            if len(self.revealed_path) == len(self.solver.path):
                self.phase = "complete"
                self.paused = True
        return True

    def single_step(self):
        self.paused = True
        self.credit = 0.0
        return self.advance()

    def update(self, seconds):
        if self.paused or self.finished:
            self.credit = 0.0
            return
        self.credit += max(0.0, min(seconds, 0.1)) * self.speed
        # A bounded batch keeps event processing responsive even at high speed.
        count = min(int(self.credit), 256)
        for _ in range(count):
            if not self.advance():
                break
            self.credit -= 1
            if self.paused:
                self.credit = 0.0
                break
