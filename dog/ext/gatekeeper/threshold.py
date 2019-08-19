import collections


class Threshold(collections.namedtuple("Threshold", ["rate", "per"])):
    """A threshold is a :class:`collections.namedtuple` representing a limit of
    events per span of time.

    In a threshold, only :attr:`rate` events are allowed per :attr:`per`
    seconds.
    """

    @classmethod
    def from_string(cls, string: str) -> "Threshold":
        """Parses a string into a :class:`Threshold`.

        The string consists of two integers separated by a single slash.

        Example
        -------
        >>> parse_threshold("5/10")
        Threshold(rate=5, per=10)
        """
        try:
            rate, per = string.split("/", 1)
            if "" in (rate, per):
                raise TypeError("Invalid threshold syntax")
            return Threshold(rate=int(rate), per=float(per))
        except ValueError:
            raise TypeError("Invalid threshold syntax")
