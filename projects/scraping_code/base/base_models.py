from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    id: str
    source: str
    title: str
    url: str
    published_at: str  # ISO 8601 string
    text: str
    created_at: str    # fecha del scrap

    @staticmethod
    def now_iso() -> str:
        return datetime.utcnow().isoformat()
