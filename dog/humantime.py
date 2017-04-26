"""
Contains humantime parsing. Humantime is a human-friendly way of specifying
time durations.

Examples:

- 1hr50m: 1 hour and 50 minutes
- 5mo2w: 5 months and 2 weeks
- 3mo2w5d2h5m1s 3 months, 2 weeks, 5 days, 2 hours, 5 minutes, and 1 second

List of specifiers:

- `mo`: Month(s)
- `w`: Week(s)
- `d`: Day(s)
- `h`: Hour(s)
- `m`: Minute(s)
- `s`: Second(s)
"""

import re

humantime_patt = re.compile(r"(?P<month>(\d+)(?:mo))?(?P<week>(\d+)w)?(?P<day>"
                            r"(\d+)(?:d))?(?P<hour>(\d+)(?:h))?(?P<minute>(\d+"
                            r")(?:m))?(?P<second>(\d+)(?:s))?")


def humantime_parse(htime: str) -> int:
    """ Parses a humantime string, and returns it as seconds. """
    match = humantime_patt.match(htime)
    if not match.groups():
        return 0
    grps = []
    for match in match.groups():
        if match is None:
            grps.append(0)
        else:
            try:
                grps.append(int(match))
            except ValueError:
                grps.append(0)
    seconds = 0
    seconds += (grps[1] or 0) * 2592000  # month (30 days only)
    seconds += (grps[3] or 0) * 604800  # week
    seconds += (grps[5] or 0) * 86400  # day
    seconds += (grps[7] or 0) * 3600  # hour
    seconds += (grps[9] or 0) * 60  # minute
    seconds += (grps[11] or 0)  # seconds
    return seconds


class HumanTime:
    def __init__(self, arg):
        self.seconds = humantime_parse(arg)
        self.raw = arg
