"""MySQL keyword search helpers exposed under the ElasticSearch package."""

from .ES_func import search_mysql_literature_with_es

__all__ = [
    "search_mysql_literature_with_es",
]
