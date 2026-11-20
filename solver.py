"""Incremental breadth-first search, independent of the interface."""

from collections import deque


class MazeSolver:
    """One step processes one queued cell. A completed route includes S and E."""

    def __init__(self, maze):
        maze.validate()
        self.maze = maze.copy()
        self.queue = deque([self.maze.start])
        self.frontier = {self.maze.start}
        self.processed = set()
        self.parents = {self.maze.start: None}
        self.current = None
        self.finished = False
        self.path = None

    def step(self):
        if self.finished:
            return False
        self.current = self.queue.popleft()
        self.frontier.remove(self.current)
        self.processed.add(self.current)
        if self.current == self.maze.end:
            self.path = []
            cell = self.current
            while cell is not None:
                self.path.append(cell)
                cell = self.parents[cell]
            self.path.reverse()
            self.finished = True
        else:
            for neighbour in self.maze.neighbours(self.current):
                if neighbour not in self.parents:
                    self.parents[neighbour] = self.current
                    self.frontier.add(neighbour)
                    self.queue.append(neighbour)
            if not self.queue:
                self.finished = True
        return True

    def solve(self):
        """Finish this search and return a shortest route, or None."""
        while not self.finished:
            self.step()
        return None if self.path is None else list(self.path)
