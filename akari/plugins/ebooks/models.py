from dataclasses import dataclass
from typing import List, Optional

@dataclass(slots=True)
class URL:
    title: str
    url: str

@dataclass(slots=True)
class FileInfo:
    extension: str
    size: str
    language: Optional[str]
    library: str

@dataclass(slots=True)
class RecentDownload:
    id: str
    title: str

@dataclass(slots=True)
class SearchResult:
    id: str
    title: str
    authors: str
    file_info: FileInfo
    thumbnail: Optional[str]
    publisher: Optional[str]
    publish_date: Optional[str]

@dataclass(slots=True)
class Download:
    title: str
    description: str
    authors: str
    file_info: FileInfo
    urls: List[URL]
    thumbnail: Optional[str]
    publisher: Optional[str]
    publish_date: Optional[str]
