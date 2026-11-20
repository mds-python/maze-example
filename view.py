"""PyRobbo-inspired tile rendering, clipping, scrolling, and bitmap counters.

Sprite slicing and digit-strip rendering are adapted from Maciej Dems' PyRobbo
(2019), robbo/images.py and robbo/status.py. Distributed under GPL-3.0-or-later.
"""

import math
from pathlib import Path
import pygame

from ui_widgets import FIELD, EDGE, ACCENT, GOLD, panel

FLOOR = (37, 39, 70)
PROCESSED = (28, 71, 92)
FRONTIER = (112, 82, 37)
ROUTE = (25, 77, 69)


class SpriteAtlas:
    """Use the original 32-pixel tiles and 16×32 bitmap digits from PyRobbo."""

    def __init__(self, directory=None):
        directory = directory or Path(__file__).resolve().parent / "assets"
        self.image = pygame.image.load(str(directory / "icons.png")).convert_alpha()
        self.digits = pygame.image.load(str(directory / "digits.png")).convert_alpha()
        self.cache = {}

    def icon(self, index, size=32):
        key = index, size
        if key not in self.cache:
            # PyRobbo's sprite atlas has a two-pixel margin and 34-pixel pitch.
            rect = pygame.Rect(34 * (index % 10) + 2, 34 * (index // 10) + 2, 32, 32)
            image = pygame.Surface((32, 32), pygame.SRCALPHA)
            image.blit(self.image, (0, 0), rect)
            self.cache[key] = pygame.transform.scale(image, (size, size))
        return self.cache[key]

    def number(self, surface, value, position, places=4, scale=0.75):
        text = str(max(0, int(value))).rjust(places, "0")
        for i, digit in enumerate(text):
            key = "digit", digit, scale
            if key not in self.cache:
                image = pygame.Surface((16, 32), pygame.SRCALPHA)
                image.blit(self.digits, (0, 0), pygame.Rect(18 * int(digit), 0, 16, 32))
                self.cache[key] = pygame.transform.scale(image, (int(16 * scale), int(32 * scale)))
            surface.blit(self.cache[key], (position[0] + i * int(16 * scale), position[1]))


class MazeView:
    def __init__(self, rect, atlas):
        self.rect = pygame.Rect(rect)
        self.atlas = atlas
        self.cell_size = 32
        self.offset = [0, 0]

    def clamp(self, maze):
        for axis, cells in enumerate((maze.width, maze.height)):
            available = (self.rect.width, self.rect.height)[axis]
            total = cells * self.cell_size
            self.offset[axis] = ((available - total) // 2 if total <= available
                                 else max(available - total, min(0, self.offset[axis])))

    def fit(self, maze):
        self.cell_size = max(8, min(48, self.rect.width // maze.width,
                                    self.rect.height // maze.height))
        self.offset = [0, 0]
        self.clamp(maze)

    def pan(self, dx, dy, maze):
        self.offset[0] += dx
        self.offset[1] += dy
        self.clamp(maze)

    def zoom(self, delta, anchor, maze):
        old = self.cell_size
        new = max(8, min(64, old + delta))
        if old == new:
            return
        for axis, origin in enumerate(self.rect.topleft):
            world = (anchor[axis] - origin - self.offset[axis]) / old
            self.offset[axis] = round(anchor[axis] - origin - world * new)
        self.cell_size = new
        self.clamp(maze)

    def cell_at(self, position, maze):
        if not self.rect.collidepoint(position):
            return None
        c = (position[0] - self.rect.x - self.offset[0]) // self.cell_size
        r = (position[1] - self.rect.y - self.offset[1]) // self.cell_size
        cell = int(r), int(c)
        return cell if maze.contains(cell) else None

    def cell_rect(self, cell):
        r, c = cell
        return pygame.Rect(self.rect.x + self.offset[0] + c * self.cell_size,
                           self.rect.y + self.offset[1] + r * self.cell_size,
                           self.cell_size, self.cell_size)

    def center(self, cell):
        return self.cell_rect(cell).center

    def visible_cells(self, maze):
        first_c = max(0, -self.offset[0] // self.cell_size)
        first_r = max(0, -self.offset[1] // self.cell_size)
        last_c = min(maze.width, math.ceil((self.rect.width - self.offset[0]) / self.cell_size))
        last_r = min(maze.height, math.ceil((self.rect.height - self.offset[1]) / self.cell_size))
        return [(r, c) for r in range(first_r, last_r) for c in range(first_c, last_c)]

    def draw(self, surface, maze, playback, fonts, hover=None, editing=False):
        panel(surface, self.rect.inflate(14, 14), FIELD, EDGE)
        old_clip = surface.get_clip()
        surface.set_clip(self.rect)
        surface.fill(FIELD, self.rect)
        solver = playback.solver if playback else None
        route_indices = playback.route_indices if playback else {}
        cells = self.visible_cells(maze)
        for cell in cells:
            rect = self.cell_rect(cell)
            symbol = maze.cell(cell)
            if symbol == "#":
                surface.blit(self.atlas.icon(2, self.cell_size), rect)
                continue
            colour = FLOOR
            if solver and cell in solver.processed:
                colour = PROCESSED
            if solver and cell in solver.frontier:
                colour = FRONTIER
            if cell in route_indices:
                colour = ROUTE
            surface.fill(colour, rect)
            if self.cell_size >= 14:
                pygame.draw.rect(surface, (51, 57, 79), rect, 1)

        # A visible-cell lookup avoids scanning a huge route every frame.
        if playback:
            for cell in cells:
                index = route_indices.get(cell)
                if index is not None and index + 1 < len(playback.revealed_path):
                    next_cell = playback.revealed_path[index + 1]
                    pygame.draw.line(surface, ACCENT, self.center(cell), self.center(next_cell),
                                     max(2, self.cell_size // 6))
                if index is not None and index > 0:
                    previous = playback.revealed_path[index - 1]
                    pygame.draw.line(surface, ACCENT, self.center(previous), self.center(cell),
                                     max(2, self.cell_size // 6))
        for cell in cells:
            symbol = maze.cell(cell)
            rect = self.cell_rect(cell)
            if symbol in ("S", "E"):
                surface.blit(self.atlas.icon(52 if symbol == "S" else 15, self.cell_size), rect)
                pygame.draw.rect(surface, ACCENT if symbol == "S" else GOLD, rect, 2)
                image = fonts["small"].render(symbol, True, (255, 255, 255))
                size = min(17, self.cell_size - 2)
                image = pygame.transform.scale(image, (size, size))
                pygame.draw.rect(surface, (5, 10, 18), (rect.x + 1, rect.y + 1, size, size))
                surface.blit(image, (rect.x + 1, rect.y + 1))
        if playback and playback.revealed_path:
            cell = playback.revealed_path[-1]
            if maze.cell(cell) not in ("S", "E"):
                direction = 50
                if len(playback.revealed_path) > 1:
                    prev = playback.revealed_path[-2]
                    dr, dc = cell[0] - prev[0], cell[1] - prev[1]
                    direction = 52 if dr > 0 else 56 if dr < 0 else 54 if dc < 0 else 50
                direction += int(pygame.time.get_ticks() // 180) % 2
                surface.blit(self.atlas.icon(direction, self.cell_size), self.cell_rect(cell))
        if solver and playback.phase == "search" and solver.current is not None:
            pygame.draw.rect(surface, GOLD, self.cell_rect(solver.current), 2)
        if editing and hover is not None:
            pygame.draw.rect(surface, (240, 247, 255), self.cell_rect(hover), 2)
        surface.set_clip(old_clip)
