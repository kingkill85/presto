# Switches from the settings page, saved to flash only when one is switched.
import json

SETTINGS_FILE = "settings.json"
settings = {
    "leds": True,       # status LEDs: one per agent, red pulse for a failed pipeline
    "anim_leds": True,  # mood and scene lights
    "sounds": True,     # pipeline and Claude beeps
    "anim": True,       # scene sounds (fight)
    "music": True,      # Guybrush and dance songs
}
try:
    with open(SETTINGS_FILE) as f:
        settings.update(json.load(f))
except (OSError, ValueError):
    pass


def save():
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except OSError:
        pass
