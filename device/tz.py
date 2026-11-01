# German local time (CET/CEST) from the UTC that ntptime sets.
# Summer time runs from the last Sunday of March to the last Sunday of
# October, switching at 01:00 UTC.
import time


def _last_sunday(year, month):
    t = time.mktime((year, month, 31, 1, 0, 0, 0, 0))
    return t - ((time.gmtime(t)[6] + 1) % 7) * 86400


def localtime():
    now = time.time()
    year = time.gmtime(now)[0]
    summer = _last_sunday(year, 3) <= now < _last_sunday(year, 10)
    return time.gmtime(now + (7200 if summer else 3600))
