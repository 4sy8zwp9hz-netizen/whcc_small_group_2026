"""Bounded process-local failed-login limits by signed browser identity, not proxy IP."""
import threading
import time
from collections import OrderedDict, deque


class LoginLimiter:
    def __init__(self, limit=10, window=300, capacity=1024, clock=time.monotonic):
        self.limit, self.window, self.capacity, self.clock = limit, window, capacity, clock
        self.clients = OrderedDict()
        self.lock = threading.Lock()

    def blocked(self, identity):
        with self.lock:
            now = self.clock()
            bucket = self.clients.get(identity)
            if bucket is None:
                return False
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if not bucket:
                self.clients.pop(identity, None)
                return False
            self.clients.move_to_end(identity)
            return len(bucket) >= self.limit

    def failure(self, identity):
        with self.lock:
            if identity not in self.clients:
                if len(self.clients) >= self.capacity:
                    self.clients.popitem(last=False)
                self.clients[identity] = deque(maxlen=self.limit)
            self.clients[identity].append(self.clock())
            self.clients.move_to_end(identity)

    def success(self, identity):
        with self.lock:
            self.clients.pop(identity, None)
