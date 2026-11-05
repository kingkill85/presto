"""Shared game pages: pixel type, sky colours, garland and flat desk tiles."""
import time
from gamepad import A, B, START, UP, DOWN, LEFT, RIGHT
from picographics import PicoGraphics, DISPLAY_PRESTO_FULL_RES, PEN_RGB565


class GameUI:
    ROWS = 7
    def __init__(self, presto, pad, feed=None):
        self.presto, self.pad, self.feed = presto, pad, feed
        self.canvas = None

    def surface(self):
        if self.canvas is None:
            self.canvas = PicoGraphics(DISPLAY_PRESTO_FULL_RES,
                                       pen_type=getattr(self.presto, 'game_pen_type', PEN_RGB565), layers=1)
            self.canvas.set_font('bitmap8')
            from tz import localtime
            night = localtime()[3] >= 21 or localtime()[3] < 6
            rgb = (15, 20, 43) if night else (29, 43, 83)
            self.bg = self.canvas.create_pen(*rgb)
            self.tile = self.canvas.create_pen(rgb[0]+16, rgb[1]+17, rgb[2]+27)
            self.shadow = self.canvas.create_pen(rgb[0]//2, rgb[1]//2, rgb[2]//2)
            self.text = self.canvas.create_pen(255, 241, 232)
            self.muted = self.canvas.create_pen(131, 118, 156)
            self.accent = self.canvas.create_pen(255, 163, 0)
            self.leaf = self.canvas.create_pen(171, 82, 54)
        return self.canvas

    def fit(self, text, width, scale=2):
        d = self.surface()
        if d.measure_text(text, scale) <= width:
            return text
        while text and d.measure_text(text+'..', scale) > width:
            text = text[:-1]
        return text+'..'

    def draw(self, title, rows, selected, detail='', back='Zurueck'):
        d = self.surface()
        compact = title == 'SPIELMENUE'
        count, step, height = (8, 44, 38) if compact else (self.ROWS, 52, 46)
        pages = max(1, (len(rows)+count-1)//count)
        page_label = '%d / %d' % (selected//count+1, pages) if pages > 1 else ''
        page_width = d.measure_text(page_label, 2) if page_label else 0
        d.set_pen(self.bg); d.clear()
        d.set_pen(self.tile)
        for i in range(14):
            d.rectangle(((i*53+17)%232)//4*8, (40+(i*71)%178)//4*8, 8, 8)
        # The main pages' chunky garland and shadowed heading.
        d.set_pen(self.muted); d.rectangle(0, 0, 480, 4)
        for x in range(4, 480, 32):
            d.set_pen(self.accent if (x//32)%2 else self.leaf)
            d.rectangle(x+8, 4, 8, 16); d.rectangle(x, 12, 24, 8)
        d.set_pen(self.accent)
        d.rectangle(24, 43, 40, 24); d.rectangle(32, 35, 16, 8)
        d.set_pen(self.shadow); d.text(self.fit(title, 375, 4), 88, 36, scale=4)
        d.set_pen(self.text); d.text(self.fit(title, 375, 4), 84, 32, scale=4)
        d.set_pen(self.muted)
        d.text(self.fit(detail, 436-page_width-(16 if page_label else 0)), 22, 78, scale=2)
        if page_label:
            d.text(page_label, 458-page_width, 78, scale=2)
        offset = selected // count * count
        for i, row in enumerate(rows[offset:offset+count]):
            label, sub, enabled = row
            y = 108+i*step
            d.set_pen(self.accent if offset+i == selected else self.tile)
            d.rectangle(16, y, 448, height)
            d.set_pen(self.tile); d.rectangle(20, y+4, 440, height-8)
            d.set_pen(self.bg)
            for x, yy in ((16,y),(460,y),(16,y+height-4),(460,y+height-4)):
                d.rectangle(x, yy, 4, 4)
            d.set_pen(self.text if enabled else self.muted)
            d.text(self.fit(label, 414), 30, y+4 if sub else y+(height-16)//2, scale=2)
            if sub:
                d.set_pen(self.muted); d.text(self.fit(sub, 414), 30, y+(20 if compact else 25), scale=2)
        self.presto.presto.update(d)

    def choose(self, title, rows, detail='', selected=0, back='Zurueck'):
        back_index = None
        if not any(row[0] == back and row[2] for row in rows):
            back_index = len(rows)
            rows = rows + [(back, '', True)]
        selected = min(max(0, selected), max(0, len(rows)-1))
        count, step, height = (8, 44, 38) if title == 'SPIELMENUE' else (self.ROWS, 52, 46)
        drawn = None
        ready, touched = False, True
        while True:
            if self.feed:
                self.feed()
            if drawn != selected:
                self.draw(title, rows, selected, detail, back)
                drawn = selected
            held = self.pad.poll()
            touch = self.presto.touch
            touch.poll()
            touching = bool(touch.state)
            if not held and not touching:
                ready = True
            if ready:
                actions = self.pad.actions
                if rows:
                    if actions & UP: selected = (selected-1) % len(rows)
                    elif actions & DOWN: selected = (selected+1) % len(rows)
                    elif actions & LEFT: selected = max(0,selected-count)
                    elif actions & RIGHT: selected = min(len(rows)-1,selected+count)
                if self.pad.pressed & B:
                    return None
                if rows and self.pad.pressed & (A | START) and rows[selected][2]:
                    return None if selected == back_index else selected
                if touching and not touched:
                    row = (touch.y-108)//step
                    index = selected//count*count+row
                    if (16 <= touch.x < 464 and 0 <= row < count
                            and (touch.y-108)%step < height and index < len(rows)):
                        selected = index
                        if rows[index][2]:
                            return None if index == back_index else index
            touched = touching
            time.sleep_ms(16)

    def notice(self, title, detail):
        self.choose(title, [('OK', '', True)], detail)

    def confirm(self, title, detail):
        return self.choose(title, [('Abbrechen', '', True), ('Bestaetigen', '', True)], detail) == 1

    def release(self):
        while True:
            if self.feed: self.feed()
            held = self.pad.poll()
            self.presto.touch.poll()
            if not held and not self.presto.touch.state:
                return
            time.sleep_ms(16)

    def pause(self, title, zoom, slots, set_zoom, audio=None, set_volume=None):
        selected = 0
        while True:
            can_save, can_load = slots.capabilities()
            note = '' if can_save else 'Hier nicht verfuegbar'
            rows = [
                ('Fortsetzen', '', True),
                ('Speichern', note, can_save),
                ('Laden', '' if can_load else 'Hier nicht verfuegbar', can_load),
                ('Vergroesserung: '+('AN' if zoom else 'AUS'), '', True),
                ('Spiel neu starten', '', True),
                ('Zur Spiele-Auswahl', '', True),
            ]
            if audio is not None:
                rows.insert(4, ('Ton: '+(str(audio.volume)+'%' if audio.volume else 'AUS'), '', True))
            choice = self.choose('SPIELMENUE', rows, title, selected=selected, back='Fortsetzen')
            if choice is None or choice == 0:
                self.release()
                return 'resume', zoom
            selected = choice
            action = choice - 1 if audio is not None and choice > 4 else choice
            if choice == 4 and audio is not None:
                try:
                    levels = (0, 30, 60, 100)
                    set_volume(levels[(levels.index(audio.volume) + 1) % len(levels)])
                except (OSError, ValueError) as error:
                    self.notice('NICHT GESPEICHERT', str(error))
            elif action == 3:
                try:
                    set_zoom(not zoom)
                    zoom = not zoom
                except (OSError, ValueError) as error:
                    self.notice('NICHT GESPEICHERT', str(error))
            elif action in (4, 5):
                if action == 5 or self.confirm('NEUSTART?', 'Ungesicherter Fortschritt geht verloren'):
                    self.release()
                    return ('restart' if action == 4 else 'exit'), zoom
            elif action in (1, 2):
                saving = action == 1
                try:
                    infos = [slots.info(n) for n in range(1,6)]
                    slot = self.choose('SPEICHERN' if saving else 'LADEN', [
                        ('Platz %d' % (i+1), info or 'Leer', saving or info is not None)
                        for i,info in enumerate(infos)], title)
                    if slot is None:
                        continue
                    if saving and infos[slot] is not None and not self.confirm('UEBERSCHREIBEN?', 'Platz %d: %s' % (slot+1, infos[slot])):
                        continue
                    if saving: slots.save(slot+1)
                    else: slots.load(slot+1)
                    self.release()
                    return ('saved' if saving else 'loaded'), zoom
                except (OSError, ValueError, RuntimeError, MemoryError) as error:
                    self.notice('NICHT MOEGLICH', str(error))
