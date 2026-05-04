import json
import os
from typing import Any, Dict, List, Optional
import serpapi
import requests
from schemas.db_template import Literature_Metadata_Record
import re

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

####################### 处理查询结果
def _extract_cited_by_total(value: Any) -> Optional[int]:
    try:
        return Literature_Metadata_Record.model_validate({"cited_by": value}).cited_by
    except Exception:
        return None
############################### 从summary字段安全解析出author, platform, year ########################
def safe_parse_summary(summary: Any) -> tuple[str, str, str]:
    if not isinstance(summary, str) or not summary.strip():
        return "Unknown Author", "Unknown Platform", "Unknown Year"

    text = summary.strip()
    parts = [part.strip() for part in text.split(" - ", 2)]

    if len(parts) >= 2:
        author = parts[0] or "Unknown Author"
        platform_year = parts[1]
    else:
        author = text or "Unknown Author"
        platform_year = ""

    year_match = re.search(r"\b(19|20)\d{2}\b", platform_year)
    year = year_match.group(0) if year_match else "Unknown Year"

    if "," in platform_year:
        platform = platform_year.rsplit(",", 1)[0].strip()
    else:
        platform = platform_year.strip()

    if not platform:
        platform = "Unknown Platform"

    return author, platform, year


############################# 标准化元数据记录格式 ########################
def _normalize_metadata_record(record: Dict[str, Any]) -> Literature_Metadata_Record:

    author, platform, year = safe_parse_summary(record.get("publication_info", {}).get("summary", ""))

    return Literature_Metadata_Record(
        title=record.get("title", ""),
        author=author,
        platform=platform,
        year=year,
        link=record.get("link", ""),
        snippet=record.get("snippet", ""),
        cited_by=_extract_cited_by_total(record.get("cited_by")),
        source=record.get("source", "hiagent"),
        raw_payload=json.dumps(record, ensure_ascii=False),
    )

################################ 调用serpapi搜索Google Scholar ################################
def serpapi_google_scholar(
        query: str, 
        num: int = 10,
        lang: str = "zh-CN"
        ) -> List[Literature_Metadata_Record]:
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
    print("$"*10+"成功从Google Scholar获取organic_results:"+"$"*10)
    print("$"*10+"开始修改文献元数据结构......")
    normalized_list: List[Literature_Metadata_Record] = []
    for item in organic_results:
        normalized_list.append(_normalize_metadata_record(item))

    return normalized_list

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