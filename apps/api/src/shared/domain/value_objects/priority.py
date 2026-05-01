from enum import Enum


class Priority(Enum):
    URGENT = ("urgent", 0)
    HIGH = ("high", 10)
    NORMAL = ("normal", 20)
    LOW = ("low", 30)

    def __init__(self, label: str, score: int) -> None:
        self.label = label
        self.score = score
