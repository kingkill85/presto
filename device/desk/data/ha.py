# Home Assistant: weather, sun, presence, rooms and batteries.
# ha_config.py lists the entities, HA_TOKEN in secrets.py turns it on.

import network

try:
    from secrets import HA_TOKEN
    import ha_config as HAC
    from haclient import HAClient
except ImportError:
    HA_TOKEN = None
    HAC = None

client = None  # HAClient once WiFi is up
_wlan = network.WLAN(network.STA_IF)

CONDITION_DE = {
    "sunny": "SONNIG", "clear-night": "KLAR", "partlycloudy": "TEILS BEWOELKT", "cloudy": "BEWOELKT",
    "rainy": "REGEN", "pouring": "STARKREGEN", "snowy": "SCHNEE", "snowy-rainy": "SCHNEEREGEN",
    "fog": "NEBEL", "hail": "HAGEL", "lightning": "GEWITTER", "lightning-rainy": "GEWITTER",
    "windy": "WINDIG", "windy-variant": "WINDIG", "exceptional": "UNWETTER",
}
RAIN = ("rainy", "pouring", "lightning-rainy", "snowy-rainy", "hail")
SNOW = ("snowy", "snowy-rainy")
THUNDER = ("lightning", "lightning-rainy")


def _entities():
    ids = [HAC.WEATHER, HAC.SUN, HAC.PERSON]
    for _, temp, light in HAC.ROOMS:
        ids += [e for e in (temp, light) if e]
    return ids + [e for _, e in HAC.BATTERIES]


def poll(now):
    """One small non-blocking step of the Home Assistant client per frame."""
    global client
    if not HA_TOKEN:
        return
    if client is None:
        if not _wlan.isconnected():
            return
        try:
            client = HAClient(HAC.HOST, HAC.PORT, HA_TOKEN, _entities(), gap_ms=800)
        except Exception:
            return
    client.poll(now)


def ready():
    """Is there any data yet?"""
    return bool(client and client.states)


def version():
    """Counts up whenever a state changes."""
    return client.version if client else -1


def state(eid):
    return client.states.get(eid) if client and eid else None


def weather_state():
    return state(HAC.WEATHER) if HA_TOKEN else None


def sun_state():
    return state(HAC.SUN) if HA_TOKEN else None


def person_state():
    return state(HAC.PERSON) if HA_TOKEN else None


def weather():
    """(condition, night) or (None, False) without data."""
    w, sun = weather_state(), sun_state()
    return (w["state"] if w else None), bool(sun and sun["state"] == "below_horizon")


def temperature():
    w = weather_state()
    return w["attributes"].get("temperature") if w else None


def outfit():
    """(wear, rain, breath) for the current weather: wear is "hat", "shades"
    or both joined with "+"."""
    if not weather_state():
        return "", False, False
    cond, night = weather()
    t = temperature()
    wear = []
    if (t is not None and t < 3) or cond in SNOW:
        wear.append("hat")
    if t is not None and t > 26 and not night:
        wear.append("shades")
    return "+".join(wear), cond in RAIN, t is not None and t < 5


def low_batteries():
    """["LABEL 12%", ...] for every battery below HAC.LOW_BATTERY."""
    low = []
    if not HA_TOKEN:
        return low
    for label, eid in HAC.BATTERIES:
        st = state(eid)
        try:
            level = float(st["state"]) if st else 100
        except (TypeError, ValueError):
            continue
        if level < HAC.LOW_BATTERY:
            low.append("%s %d%%" % (label, level))
    return low
