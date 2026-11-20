# PyMaze attribution

The reference implementation uses Maciej Dems' PyRobbo as its UI basis, with the
author's explicit permission in the accompanying conversation.

Upstream: https://github.com/macdems/pyrobbo

Reviewed revision: `f11b69edfb65b171792a76a259bcf7aab0abb6a4` (2026-11-20).

PyRobbo source files carry Copyright (C) 2019 Maciej Dems and
GPL-3.0-or-later notices. The full licence is included as `LICENSE`.

| PyRobbo element | Adaptation here |
| --- | --- |
| `robbo/images.py` | 34-pixel-pitch atlas slicing into 32×32 icons, plus 16×32 bitmap digits, adapted in `view.SpriteAtlas` |
| `robbo/status.py` | Digit-by-digit numeric HUD rendering, adapted in `view.SpriteAtlas.number` |
| `robbo/__init__.py` | Scaled, resizable logical display and fullscreen/window modes |
| `robbo/board.py`, `robbo/game.py` | Clipped tile-board presentation, viewport scrolling, event/clock loop and keyboard interaction as UI basis |
| `robbo/skins/default/icons.png` | Included unchanged as `assets/icons.png` |
| `robbo/skins/default/digits.png` | Included unchanged as `assets/digits.png` |

PyRobbo's README credits the **GNU Robbo project**
(http://gnurobbo.sourceforge.net/) as the source of the graphics and level data.
Only the two graphics files listed above are used in this application; none of
the original level data or sounds are included.

Maze data/validation, the incremental BFS solver, playback state, editor/history,
Pygame dialogs, and reference verification were added for the Maze Solver task.
Modified UI/rendering code is identified in the relevant module docstrings.

The original Atari Robbo game is credited by PyRobbo to Janusz Pelc of LK. Avalon.
