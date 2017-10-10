from time import monotonic


class Timer:
    def __init__(self):
        self.before: float = None
        self.after: float = None

    def __enter__(self):
        self.before = monotonic()
        return self

    def __exit__(self, _, __, ___):
        self.after = monotonic()

    @property
    def interval(self):
        return self.after - self.before
