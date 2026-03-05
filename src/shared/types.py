from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class TrendItem:
    name: str
    url: str
    description: str
    source: str
    daily_stars: int = 0
    language: str = ""
    # Make it compatible with dictionary access for legacy code temporarily
    def get(self, key, default=None):
        return getattr(self, key, default)
    def __getitem__(self, key):
        return getattr(self, key)

@dataclass
class Article:
    title: str
    body: str
    lang: str = "ja" # "ja" or "en"
    slug: str = ""
    source_url: str = ""
    tool_name: str = ""
    tags: List[str] = field(default_factory=list)
    ogp_url: Optional[str] = None
