import re

def humantime_parse(htime):
    regex = re.compile(r"(?P<month>(\d+)(?:mo))?(?P<week>(\d+)w)?(?P<day>(\d+)(?:d))?(?P<hour>(\d+)(?:h))?(?P<minute>(\d+)(?:m))?(?P<second>(\d+)(?:s))?")
    match = regex.match(htime)
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
