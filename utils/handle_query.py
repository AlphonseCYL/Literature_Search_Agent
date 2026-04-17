
from typing import Any, Dict


def handle_query(
        scholar_query: str,  
        num: int = 5
        ) -> str:

    cleaned_query = scholar_query.strip('"')
    if not cleaned_query.strip():
        cleaned_query = "default search" # 或者抛出异常
        
    return cleaned_query