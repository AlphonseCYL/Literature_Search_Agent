

def handle_query(
        scholar_query: str,  
        ) -> str:
    '''
    处理和清洗搜索查询字符串query，去除多余的引号和空白等
    '''
    cleaned_query = scholar_query.strip('"')
    if not cleaned_query.strip():
        cleaned_query = "default search" # 或者抛出异常
        
    return cleaned_query

