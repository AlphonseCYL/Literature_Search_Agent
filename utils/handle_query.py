
from .json_Unicode_2dict import normalize_json_to_dict

def handle_query(
        scholar_query: str,  
        ) -> str:

    cleaned_query = scholar_query.strip('"')
    if not cleaned_query.strip():
        cleaned_query = "default search" # 或者抛出异常
        
    return cleaned_query

