# Copy to ha_config.py on the device and fill in your entities.
# The token goes into secrets.py as HA_TOKEN.
# Plain HTTP on the local network: fast, and no TLS handshake on the Presto.
HOST = "192.168.1.10"  # Home Assistant on your LAN
PORT = 8123

WEATHER = "weather.forecast_home"
SUN = "sun.sun"
PERSON = "person.me"

# (label, temperature entity or None, light entity or None). Climate entities
# also show a flame while heating.
ROOMS = (
    ("LIVING", "climate.living_room", "light.living_room"),
    ("OFFICE", "sensor.office_temperature", "light.office"),
    ("KITCHEN", None, "light.kitchen"),
)

# (label, battery sensor): warned about below LOW_BATTERY percent
BATTERIES = (
    ("REMOTE", "sensor.remote_battery"),
)
LOW_BATTERY = 25
