"""In-process topics, standing in for Pub/Sub in the local version (the cloud version uses Pub/Sub)."""
from collections import deque
from typing import Any, Deque, Dict


class Bus:
    def __init__(self):
        self.topics: Dict[str, Deque[Any]] = {}
        self.published: Dict[str, int] = {}

    def publish(self, topic: str, message: Any) -> None:
        self.topics.setdefault(topic, deque()).append(message)
        self.published[topic] = self.published.get(topic, 0) + 1

    def drain(self, topic: str):
        queue = self.topics.get(topic, deque())
        while queue:
            yield queue.popleft()
