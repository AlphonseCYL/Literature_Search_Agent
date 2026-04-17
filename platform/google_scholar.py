import json
import os
from typing import Any, Dict, List
import serpapi
import requests

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()

DASHSCOPE_URL = os.getenv(
    "DASHSCOPE_URL",
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")




def search_google_scholar(
        query: str, 
        num: int = 10,
        lang: str = "zh-CN"
        ) -> List[Dict[str, Any]]:
    """Search Google Scholar via SerpAPI and return simplified results."""
    if not SERPAPI_API_KEY:
        raise RuntimeError("缺失 SERPAPI_API_KEY")

    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": max(1, min(int(num), 20)),# 1-20篇范围内
        "hl": lang,
    }

    response = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    # 打印网址
    print("$"*20 + "\n" + response.url)
    f = open("show.txt", "w", encoding="utf-8")
    f.write(response.url)
    f.close()

    response.raise_for_status()

    data = response.json()
    results: List[Dict[str, Any]] = []
    for item in data.get("organic_results", []):
        results.append(
            {
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "publication_info": item.get("publication_info"),
                "cited_by": item.get("inline_links", {}).get("cited_by", {}).get("total"),
            }
        )
    return results



def serpapi_google_scholar(
        query: str, 
        num: int = 10,
        lang: str = "zh-CN"
        ) -> List[Dict[str, Any]]:
    """Search Google Scholar via SerpAPI and return simplified results."""
    if not SERPAPI_API_KEY:
        raise RuntimeError("缺失 SERPAPI_API_KEY")

    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "as_ylo": "1990", # 限制为2020年及以后的文献
        "as_yhi": "2026", # 限制2026年及以前的文献
        "num": max(1, min(int(num), 20)),# 1-20篇范围内
        "hl": lang,
    }
    client = serpapi.Client(api_key=SERPAPI_API_KEY)
    results = client.search(params)
    organic_results = results["organic_results"]
    print("$"*20+"调用的是serpapi_google_scholar函数")

    return organic_results

############################
def handle_literature_query(
        scholar_query: str, 
        model: str = "qwen-plus", 
        num: int = 5
        )-> Dict[str, Any]:
    
    """Minimal end-to-end flow: query -> qwen-plus rewrite -> Google Scholar search."""

    cleaned_query = scholar_query.strip('"')
    results = search_google_scholar(query=cleaned_query, num=num)
    if not cleaned_query.strip():
        cleaned_query = "default search" # 或者抛出异常
        
    return {
        "scholar_query": scholar_query,
        "cleaned_query": cleaned_query,
        "results": results,
    }
################################

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Minimal qwen-plus + Google Scholar search")
    parser.add_argument("--query", required=True, help="User literature search query")
    parser.add_argument("--model", default="qwen-plus", help="LLM model name")
    parser.add_argument("--num", type=int, default=5, help="Max results (1-20)")
    parser.add_argument("--lang", default="zh-CN", help="Language for Google Scholar results (e.g., 'en', 'zh-CN')")
    args = parser.parse_args()

    # output = handle_literature_query(args.query, model=args.model, num=args.num)
    output = serpapi_google_scholar(args.query, num=args.num, lang=args.lang)
    print(json.dumps(output, ensure_ascii=False, indent=2))

    # 运行示例：
    # python platform/google_scholar.py --query "深度学习在计算机视觉中的应用" --num 5 --lang zh-CN