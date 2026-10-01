"""Who's in a chat room right now, for "3 here now".

In memory and approximate on purpose: a viewer counts while their open chat
window keeps polling, and drops out TTL seconds after it stops. Rooms and
viewers per room are capped (LRU), so random ids can't grow memory without
bound. Single-process state, like the rate limiter.
"""

import re
import time
from collections import OrderedDict
from collections.abc import Callable

TTL_SECONDS = 20.0
MAX_ROOMS = 50_000
MAX_VIEWERS_PER_ROOM = 5_000
VIEWER_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class Presence:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._rooms: OrderedDict[str, OrderedDict[str, float]] = OrderedDict()

    def touch(self, room: str, viewer: str | None) -> int:
        """Record that `viewer` is looking at `room`; returns how many are here."""
        now = self._clock()
        viewers = self._rooms.get(room)
        if viewers is None:
            viewers = self._rooms[room] = OrderedDict()
            if len(self._rooms) > MAX_ROOMS:
                self._rooms.popitem(last=False)
        else:
            self._rooms.move_to_end(room)

        if viewer and VIEWER_ID.match(viewer):
            viewers[viewer] = now
            viewers.move_to_end(viewer)
            if len(viewers) > MAX_VIEWERS_PER_ROOM:
                viewers.popitem(last=False)
        # Oldest first, so expired viewers sit at the front.
        while viewers and next(iter(viewers.values())) < now - TTL_SECONDS:
            viewers.popitem(last=False)
        return len(viewers)


presence = Presence()
