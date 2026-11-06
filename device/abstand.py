# Abstand: shows the VL53L1X time-of-flight sensor (0x29) live. A beam runs
# from the sensor to whatever it sees, with the distance and a short history.
import time

from desk.gfx import display, draw_art, pen, presto, DIM_PEN, TEXT_PEN
from sensor_app import Exit, bus, header, leave, pace, panel
from vl53l1x import VL53L1X, OK, SIGNAL, SIGMA

ICON = ("#....", "#.#.#", "#####", "#....", "#....")
ACCENT = pen((41, 173, 255))
BEAM = pen((255, 0, 77))
TARGET = pen((255, 163, 0))
WARN = pen((255, 236, 39))
SENSOR = pen((194, 195, 199))
NEAR = pen((255, 0, 77))
MID = pen((255, 163, 0))
FAR = pen((0, 228, 54))
DARK = pen((15, 22, 45))

SCALES = (500, 1000, 2000, 4000)  # mm, the beam picks the smallest that fits
HISTORY = 52                      # 4 px columns in the graph
GX, GY, GW, GH = 12, 168, 216, 60


def text_mm(mm):
    if mm < 1000:
        return "%d cm" % ((mm + 5) // 10)
    return "%d.%02d m" % (mm // 1000, (mm % 1000 + 5) // 10)


def colour_for(mm):
    return NEAR if mm < 300 else MID if mm < 1000 else FAR


def draw(mm, status, shown, scale, history, now, alive):
    header("ABSTAND", ACCENT, ICON)
    # Big reading
    panel(12, 44, 216, 60)
    if not alive:
        display.set_pen(WARN)
        display.text("Sensor fehlt", 24, 66, -1, 2)
    elif mm is None:
        display.set_pen(DIM_PEN)
        display.text("nichts im Blick", 24, 66, -1, 2)
    else:
        label = text_mm(shown)
        w = display.measure_text(label, 5)
        display.set_pen(DARK)
        display.text(label, 120 - w // 2 + 2, 56, -1, 5)
        display.set_pen(TEXT_PEN)
        display.text(label, 120 - w // 2, 54, -1, 5)
        if status in (SIGNAL, SIGMA):
            display.set_pen(WARN)
            display.text("schwaches Signal", 24, 92, -1, 1)
    # Beam from the sensor to the target, on a ruler of the current scale
    panel(12, 108, 216, 54)
    draw_art(("##", "##", "##", "##", "##"), 16, 116, 4, SENSOR)
    x0, x1 = 28, 220
    display.set_pen(DIM_PEN)
    for i in range(5):
        x = x0 + (x1 - x0) * i // 4
        display.rectangle(x // 2 * 2, 140, 2, 6)
    lo = "0"
    hi = text_mm(scale)
    display.text(lo, x0, 150, -1, 1)
    display.text(hi, x1 - display.measure_text(hi, 1), 150, -1, 1)
    if alive and mm is not None:
        tx = x0 + (x1 - x0 - 8) * min(shown, scale) // scale
        tx = tx // 4 * 4
        phase = (now // 60) % 3
        display.set_pen(BEAM)
        for x in range(x0 + phase * 4, tx, 12):
            display.rectangle(x, 124, 4, 4)
        display.set_pen(TARGET)
        display.rectangle(tx, 116, 8, 20)
    # History graph, newest on the right
    panel(GX, GY, GW, GH)
    n = len(history)
    for i in range(n):
        v = history[i]
        if v is None:
            continue
        h = max(4, (GH - 8) * min(v, scale) // scale // 4 * 4)
        display.set_pen(colour_for(v))
        display.rectangle(GX + 4 + (HISTORY - n + i) * 4, GY + GH - 4 - h, 4, h)


def main():
    i2c = bus()
    sensor = VL53L1X(i2c)
    exit_ = Exit(i2c)
    history = []
    mm = status = None
    shown = 0.0
    scale = SCALES[0]
    last_sample = time.ticks_ms()
    while True:
        now = time.ticks_ms()
        if exit_.back(now):
            leave(sensor)
        reading = sensor.poll(now)
        if not sensor.ready:
            mm = None
        elif reading is not None:
            mm, status = reading
            if status not in (OK, SIGNAL, SIGMA):
                mm = None
            if mm is not None:
                shown = mm if not shown else shown + (mm - shown) * 0.5
                for s in SCALES:
                    scale = s
                    if mm <= s * 9 // 10:
                        break
        if time.ticks_diff(now, last_sample) >= 120:
            last_sample = now
            history.append(int(shown) if mm is not None else None)
            if len(history) > HISTORY:
                history.pop(0)
        draw(mm, status, int(shown), scale, history, now, sensor.ready)
        presto.update()
        pace(now)


main()
