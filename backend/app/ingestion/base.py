from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ParsedChunk:
    text: str
    source_type: str
    source_ref: str
    author: str | None = None
    author_aliases: list[str] = field(default_factory=list)
    timestamp: datetime | None = None
    topics: list[str] = field(default_factory=list)
    chunk_metadata: dict = field(default_factory=dict)


class BaseConnector(ABC):
    @abstractmethod
    def source_type(self) -> str: ...

    @abstractmethod
    def parse(self, source_input) -> list[ParsedChunk]: ...

    @abstractmethod
    def extract_members(self, source_input) -> list[dict]: ...
