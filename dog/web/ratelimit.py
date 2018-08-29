from time import monotonic


class Ratelimiter:
    def __init__(self, times, per) -> None:
        self.times = times
        self.per = per
        self.buckets = {}

    def check(self, token):
        if token not in self.buckets:
            self.buckets[token] = [monotonic(), 1]
            return False, None

        last_updated, times = self.buckets[token]

        if monotonic() - last_updated > self.per:
            # We can reset the amount of times hit, enough time has passed.
            self.buckets[token] = [monotonic(), 1]
            return False, None

        # Update last updated timestamp and number of times hit:
        self.buckets[token][0] = monotonic()
        self.buckets[token][1] += 1

        if times + 1 > self.times:
            # That's too much.
            time_remaining = self.per - (monotonic() - last_updated)
            return True, time_remaining

        # Still below the limit, we're good.
        return False, None
