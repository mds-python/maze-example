"""Small Pygame-only controls and dialogs. No native GUI toolkit is used."""

from pathlib import Path
import pygame

SCREEN_SIZE = (1280, 832)
BG = (7, 10, 18)
PANEL = (18, 25, 39)
FIELD = (8, 13, 23)
EDGE = (57, 72, 98)
TEXT = (226, 232, 244)
MUTED = (146, 161, 184)
ACCENT = (87, 226, 183)
GOLD = (244, 191, 84)
RED = (255, 130, 124)


def label(surface, font, text, position, colour=TEXT, width=None):
    text = str(text)
    if width is not None and font.size(text)[0] > width:
        while text and font.size(text + "…")[0] > width:
            text = text[:-1]
        text = text + "…" if font.size("…")[0] <= width else ""
    surface.blit(font.render(text, True, colour), position)


def wrapped(font, text, width):
    lines = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = (line + " " + word).strip()
            if line and font.size(candidate)[0] > width:
                lines.append(line)
                line = ""
            # Paths and filenames can be longer than an entire dialog line.
            while font.size(word)[0] > width:
                length = 1
                while length < len(word) and font.size(word[:length + 1])[0] <= width:
                    length += 1
                lines.append(word[:length])
                word = word[length:]
            line = (line + " " + word).strip()
        lines.append(line)
    return lines


def panel(surface, rect, colour=PANEL, border=EDGE):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, colour, rect)
    pygame.draw.rect(surface, border, rect, 1)
    pygame.draw.line(surface, (76, 89, 112), rect.topleft, (rect.right - 1, rect.top))


class Button:
    def __init__(self, rect, text, value=None, primary=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.value = value
        self.primary = primary
        self.enabled = True
        self.selected = False

    def hit(self, position):
        return self.enabled and self.rect.collidepoint(position)

    def draw(self, surface, font):
        hover = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())
        colour = (30, 74, 65) if self.primary or self.selected else (29, 40, 58)
        if hover:
            colour = tuple(min(255, c + 13) for c in colour)
        if not self.enabled:
            colour = (20, 28, 41)
        panel(surface, self.rect, colour, ACCENT if self.selected or self.primary else EDGE)
        image = font.render(self.text, True, TEXT if self.enabled else (90, 102, 124))
        surface.blit(image, image.get_rect(center=self.rect.center))


class TextInput:
    def __init__(self, rect, text=""):
        self.rect = pygame.Rect(rect)
        self.text = str(text)
        self.cursor = len(self.text)
        self.active = False
        self.select_all = False

    def focus(self):
        self.active = True
        self.select_all = True
        self.cursor = len(self.text)

    def insert(self, text):
        text = text.replace("\x00", "").replace("\r", "").replace("\n", "")
        if self.select_all:
            self.text, self.cursor = "", 0
        self.text = (self.text[:self.cursor] + text + self.text[self.cursor:])[:4096]
        self.cursor = min(self.cursor + len(text), len(self.text))
        self.select_all = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.focus()
                return True
        if not self.active:
            return False
        if event.type == pygame.TEXTINPUT:
            self.insert(event.text)
            return True
        if event.type != pygame.KEYDOWN:
            return False
        ctrl = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
        if ctrl and event.key == pygame.K_a:
            self.select_all = True
        elif ctrl and event.key == pygame.K_v:
            try:
                if not pygame.scrap.get_init():
                    pygame.scrap.init()
                data = pygame.scrap.get(pygame.SCRAP_TEXT)
                if data:
                    self.insert(data.decode("utf-8", errors="replace"))
            except pygame.error:
                pass  # Clipboard support depends on the SDL window backend.
        elif event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
            if self.select_all:
                self.text, self.cursor = "", 0
            elif event.key == pygame.K_BACKSPACE and self.cursor:
                self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
            elif event.key == pygame.K_DELETE:
                self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
            self.select_all = False
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_HOME, pygame.K_END):
            if event.key == pygame.K_LEFT:
                self.cursor = max(0, self.cursor - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursor = min(len(self.text), self.cursor + 1)
            else:
                self.cursor = 0 if event.key == pygame.K_HOME else len(self.text)
            self.select_all = False
        else:
            return False
        return True

    def draw(self, surface, font):
        panel(surface, self.rect, FIELD, ACCENT if self.active else EDGE)
        old_clip = surface.get_clip()
        surface.set_clip(self.rect.inflate(-10, -6))
        cursor_x = font.size(self.text[:self.cursor])[0]
        offset = max(0, cursor_x - self.rect.width + 22)
        origin = self.rect.x + 8 - offset
        if self.select_all:
            pygame.draw.rect(surface, (46, 70, 99),
                             (origin, self.rect.y + 5, font.size(self.text)[0], self.rect.height - 10))
        label(surface, font, self.text, (origin, self.rect.y + 8))
        if self.active and pygame.time.get_ticks() % 1000 < 650:
            pygame.draw.line(surface, ACCENT, (origin + cursor_x, self.rect.y + 6),
                             (origin + cursor_x, self.rect.bottom - 6))
        surface.set_clip(old_clip)


class Dialog:
    def __init__(self, title, message="", width=660, height=320, on_result=None):
        self.rect = pygame.Rect((SCREEN_SIZE[0] - width) // 2, (SCREEN_SIZE[1] - height) // 2,
                                width, height)
        self.title, self.message = title, message
        self.done, self.result = False, None
        self.on_result = on_result
        self.buttons = []

    def add_buttons(self, choices):
        self.buttons = []
        for i, (text, value) in enumerate(choices):
            x = self.rect.right - 24 - (len(choices) - i) * 124
            self.buttons.append(Button((x, self.rect.bottom - 62, 112, 36), text, value,
                                       primary=i == len(choices) - 1))

    def finish(self, result):
        self.result, self.done = result, True

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.finish(None)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if button.hit(event.pos):
                    self.finish(button.value)

    def draw_base(self, surface, fonts):
        veil = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        veil.fill((0, 0, 0, 195))
        surface.blit(veil, (0, 0))
        panel(surface, self.rect, PANEL, ACCENT)
        label(surface, fonts["heading"], self.title, (self.rect.x + 24, self.rect.y + 20))
        for i, line in enumerate(wrapped(fonts["normal"], self.message, self.rect.width - 48)):
            label(surface, fonts["normal"], line, (self.rect.x + 24, self.rect.y + 66 + i * 25))
        for button in self.buttons:
            button.draw(surface, fonts["normal"])

    def draw(self, surface, fonts):
        self.draw_base(surface, fonts)


class MessageDialog(Dialog):
    def __init__(self, title, message, on_result=None):
        super().__init__(title, message, width=760, height=390, on_result=on_result)
        self.add_buttons([("OK", True)])

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.finish(True)
        else:
            super().handle_event(event)


class ConfirmDialog(Dialog):
    def __init__(self, title, message, action="Continue", on_result=None):
        super().__init__(title, message, width=720, height=310, on_result=on_result)
        self.add_buttons([("Cancel", False), (action, True)])

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_y:
            self.finish(True)
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_n, pygame.K_RETURN):
            self.finish(False)  # Enter defaults to the non-destructive option.
        else:
            super().handle_event(event)


class FormDialog(Dialog):
    def __init__(self, title, fields, validate=None, on_result=None):
        super().__init__(title, "Choose dimensions (1 to 512 cells per side).", width=640,
                         height=360, on_result=on_result)
        self.fields = []
        for i, (name, value) in enumerate(fields):
            self.fields.append((name, TextInput((self.rect.x + 205, self.rect.y + 112 + i * 54,
                                                self.rect.width - 230, 38), value)))
        self.focused, self.error = 0, ""
        self.fields[0][1].focus()
        self.validate = validate
        self.add_buttons([("Cancel", None), ("Create", True)])

    def accept(self):
        values = {name: field.text for name, field in self.fields}
        self.error = self.validate(values) if self.validate else ""
        if not self.error:
            self.finish(values)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.accept()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            step = -1 if event.mod & pygame.KMOD_SHIFT else 1
            self.focused = (self.focused + step) % len(self.fields)
            for i, (_, field) in enumerate(self.fields):
                field.active = i == self.focused
            self.fields[self.focused][1].focus()
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if button.hit(event.pos):
                    self.accept() if button.value else self.finish(None)
                    return
            for i, (_, field) in enumerate(self.fields):
                field.active = field.rect.collidepoint(event.pos)
                if field.active:
                    self.focused = i
        for _, field in self.fields:
            field.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.finish(None)

    def draw(self, surface, fonts):
        self.draw_base(surface, fonts)
        for name, field in self.fields:
            label(surface, fonts["normal"], name, (self.rect.x + 26, field.rect.y + 9))
            field.draw(surface, fonts["normal"])
        label(surface, fonts["small"], self.error, (self.rect.x + 26, self.rect.bottom - 100), RED,
              self.rect.width - 52)


class FileDialog(Dialog):
    """A Pygame file browser, with an editable full path and no native dialog."""

    ROW_HEIGHT = 27

    def __init__(self, initial, save=False, on_result=None):
        super().__init__("Save ASCII maze" if save else "Open ASCII maze", width=920,
                         height=650, on_result=on_result)
        self.save = save
        initial = Path(initial).expanduser()
        self.directory = initial if initial.is_dir() else initial.parent
        if not self.directory.is_dir():
            self.directory = Path.cwd()
        self.directory = self.directory.resolve()
        self.basename = initial.name if save and not initial.is_dir() else "untitled.txt"
        value = self.directory / self.basename if save else initial
        self.path_input = TextInput((self.rect.x + 24, self.rect.y + 68,
                                     self.rect.width - 150, 38), str(value))
        self.path_input.focus()
        self.up = Button((self.rect.right - 108, self.rect.y + 68, 84, 38), "Up")
        self.list_rect = pygame.Rect(self.rect.x + 24, self.rect.y + 128, self.rect.width - 48, 365)
        self.entries, self.selected, self.scroll = [], -1, 0
        self.error, self.last_click = "", (-1, -1000)
        self.refresh()
        self.add_buttons([("Cancel", None), ("Save" if save else "Open", True)])

    def refresh(self):
        try:
            self.entries = sorted((p for p in self.directory.iterdir()
                                   if not p.name.startswith(".") and (p.is_dir() or p.suffix.lower() == ".txt")),
                                  key=lambda p: (not p.is_dir(), p.name.casefold()))
            self.error = ""
        except OSError as error:
            self.entries, self.error = [], str(error)
        self.selected, self.scroll = -1, 0

    def navigate(self, directory):
        self.directory = directory.resolve()
        self.path_input.text = str(self.directory / self.basename) if self.save else str(self.directory)
        self.path_input.cursor = len(self.path_input.text)
        self.path_input.select_all = False
        self.refresh()

    def accept(self):
        if not self.path_input.text.strip():
            self.error = "Enter a file path."
            return
        path = Path(self.path_input.text).expanduser()
        if not path.is_absolute():
            path = self.directory / path
        try:
            if path.is_dir():
                self.navigate(path)
                return
            if self.save and not path.suffix:
                path = path.with_suffix(".txt")
            self.finish(path)
        except (OSError, ValueError) as error:
            self.error = str(error)

    def select(self, index):
        if 0 <= index < len(self.entries):
            self.selected = index
            self.path_input.text = str(self.entries[index])
            self.path_input.cursor = len(self.path_input.text)
            self.path_input.select_all = False

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.finish(None)
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.accept()
                return
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                index = self.selected + (-1 if event.key == pygame.K_UP else 1)
                self.select(max(0, min(len(self.entries) - 1, index)))
                visible = self.list_rect.height // self.ROW_HEIGHT
                self.scroll = max(0, min(self.scroll, self.selected))
                self.scroll = max(self.scroll, self.selected - visible + 1)
                return
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(max(0, len(self.entries) - 1), self.scroll - event.y * 3))
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.up.hit(event.pos):
                self.navigate(self.directory.parent)
                return
            for button in self.buttons:
                if button.hit(event.pos):
                    self.accept() if button.value else self.finish(None)
                    return
            if self.list_rect.collidepoint(event.pos):
                index = self.scroll + (event.pos[1] - self.list_rect.y) // self.ROW_HEIGHT
                if index < len(self.entries):
                    self.select(index)
                    now = pygame.time.get_ticks()
                    if self.last_click[0] == index and now - self.last_click[1] < 400:
                        self.accept()
                    self.last_click = index, now
                return
        self.path_input.handle_event(event)

    def draw(self, surface, fonts):
        self.draw_base(surface, fonts)
        self.path_input.draw(surface, fonts["normal"])
        self.up.draw(surface, fonts["normal"])
        panel(surface, self.list_rect, FIELD)
        old_clip = surface.get_clip()
        surface.set_clip(self.list_rect.inflate(-4, -4))
        count = self.list_rect.height // self.ROW_HEIGHT
        for offset, path in enumerate(self.entries[self.scroll:self.scroll + count]):
            index = self.scroll + offset
            y = self.list_rect.y + offset * self.ROW_HEIGHT + 3
            if index == self.selected:
                pygame.draw.rect(surface, (35, 61, 79),
                                 (self.list_rect.x + 2, y, self.list_rect.width - 4, self.ROW_HEIGHT))
            prefix = "[DIR]  " if path.is_dir() else "       "
            label(surface, fonts["normal"], prefix + path.name,
                  (self.list_rect.x + 10, y + 4), ACCENT if path.is_dir() else TEXT,
                  self.list_rect.width - 25)
        surface.set_clip(old_clip)
        label(surface, fonts["small"], "Double-click a folder or file. You can also type any full path.",
              (self.rect.x + 24, self.list_rect.bottom + 20), MUTED)
        label(surface, fonts["small"], "The list shows folders and .txt files. Esc cancels; Enter opens or saves.",
              (self.rect.x + 24, self.list_rect.bottom + 43), MUTED)
        label(surface, fonts["small"], self.error, (self.rect.x + 24, self.rect.bottom - 95), RED,
              self.rect.width - 48)
