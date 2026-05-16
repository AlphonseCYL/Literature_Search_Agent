from __future__ import annotations

import json
import os
import re
from typing import Any, Sequence

from schemas.db_template import Literature_Metadata_Record

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv()


DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_MODEL = "qwen-plus"
MAX_PROMPT_SNIPPET_LENGTH = 500


class QwenFilterError(RuntimeError):
    """Raised when Qwen cannot complete or return a valid filtering result."""

# 核心函数
def filter_literature_records(
    literature_records: Sequence[Any],
    *,
    query: str,
    model: str | None = None,
    max_selected: int | None = None,
) -> list[Literature_Metadata_Record]:
    """Filter Redis literature records with Qwen according to a natural query.

    The returned records keep the original ``Literature_Metadata_Record`` shape.
    Qwen is only used to rank/select candidates; scores and reasons are not
    added to the downstream data model.
    """

    normalized_records = _normalize_records(literature_records)
    cleaned_query = _normalize_query(query)
    if not normalized_records:
        return []

    selected_limit = _normalize_max_selected(max_selected, cleaned_query)
    # 构造prompt
    prompt = _build_filter_prompt(
        query=cleaned_query,
        records=normalized_records,
        max_selected=selected_limit,
    )
    # 调用大模型
    content = _call_LLM(prompt, model=model)
    print("\nfrom filter_literature_records")
    print("LLM 筛选输出：\n" + content + "\n")
    selected_indices = _parse_selected_indices(content, candidate_count=len(normalized_records))

    if selected_limit is not None:
        selected_indices = selected_indices[:selected_limit]

    return [normalized_records[index] for index in selected_indices]


def _normalize_records(records: Sequence[Any]) -> list[Literature_Metadata_Record]:
    normalized: list[Literature_Metadata_Record] = []
    for record in records:
        try:
            if isinstance(record, Literature_Metadata_Record):
                normalized.append(record)
            elif isinstance(record, str):
                normalized.append(Literature_Metadata_Record.model_validate_json(record))
            else:
                normalized.append(Literature_Metadata_Record.model_validate(record))
        except Exception as exc:
            raise ValueError(f"invalid literature record: {exc}") from exc
    return normalized


def _normalize_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required and must be a non-empty string")
    return query.strip()


def _normalize_max_selected(max_selected: int | None, query: str) -> int | None:
    if max_selected is not None:
        if not isinstance(max_selected, int) or max_selected <= 0:
            raise ValueError("max_selected must be a positive integer")
        return max_selected
    return _infer_requested_count(query)


def _infer_requested_count(query: str) -> int | None:
    '''
    输入 query = "我想看10篇关于大模型的论文" -> 函数返回 10
    输入 query = "帮我总结三篇最新的文献" -> 函数返回 3
    输入 query = "关于深度学习的最新进展"（没提数量） -> 函数返回 None
    '''
    counts = [int(match) for match in re.findall(r"(\d+)\s*篇", query)]
    counts.extend(_chinese_count_to_int(match) for match in re.findall(r"([一二两三四五六七八九十]+)\s*篇", query))
    counts = [count for count in counts if count is not None and count > 0]
    return sum(counts) if counts else None


def _chinese_count_to_int(text: str) -> int | None:
    digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return digits.get(text)


def _build_filter_prompt(
    *,
    query: str,
    records: Sequence[Literature_Metadata_Record],
    max_selected: int | None,
) -> str:
    candidates = []
    for index, record in enumerate(records):
        data = record.model_dump()
        candidates.append(
            {
                "index": index,
                "title": data["title"],
                "author": data["author"],
                "platform": data["platform"],
                "year": data["year"],
                "snippet": data["snippet"][:MAX_PROMPT_SNIPPET_LENGTH],
                "cited_by": data["cited_by"],
                "source": data["source"],
                "link": data["link"],
            }
        )

    limit_text = (
        f"最多选择 {max_selected} 篇；如果 query 中有中文/英文数量要求，必须分别满足，不能用其他语言凑数。"
        if max_selected is not None
        else "根据 query 自行判断合适数量；如果 query 中没有数量要求，优先选择最相关的少量高质量结果。"
    )

    return f"""
你是论文检索助手的文献筛选器。请根据用户 query 对 Redis 暂存的候选文献做相似度评分和筛选。

用户 query:
{query}

筛选硬性要求:
1. 必须优先满足 query 中明确提到的数量、语言、年份/近几年、类别要求。
2. 类别要求包括但不限于: 学术论文、期刊、会议、综述、应用文章；如果 query 未提及类别，可自行判断最合适的学术文献。
3. 语言可根据标题、摘要、平台、来源和链接综合判断；明确要求中文/英文数量时必须尽量严格匹配。
4. 主题相关性最重要，年份、方法、场景、对象也要一起考虑。
5. 不满足 query 硬性条件的文献不要选择，除非候选集中没有足够结果；这种情况下只选择最接近的结果，最少选择1篇最贴近 query 要求的。
6. {limit_text}

候选文献 JSON:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

只返回严格 JSON，不要 Markdown，不要解释。格式如下:
{{
  "selected": [
    {{"index": 0, "score": 0.95, "reason": "简短中文理由"}}
  ]
}}
要求:
- index 必须来自候选文献 JSON 的 index。
- score 是 0 到 1 的相关性分数，按从高到低排序。
- selected 可以为空数组。
""".strip()


def _call_LLM(prompt: str, *, model: str | None = None) -> str:
    '''
    输出格式：
    {
        "selected": [
                {{"index": 0, "score": 0.95, "reason": "简短中文理由"}}
        ]
    }
    '''
    try:
        from openai import OpenAI
    except Exception as exc:
        raise QwenFilterError("openai package is required to call LLM") from exc

    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise QwenFilterError("DASHSCOPE_API_KEY or OPENAI_API_KEY is required")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("BASE_URL", DEFAULT_QWEN_BASE_URL),
    )

    try:
        completion = client.chat.completions.create(
            model=model or os.getenv("LLM_MODEL", DEFAULT_QWEN_MODEL),
            messages=[
                {
                    "role": "system",
                    "content": "你只输出严格 JSON，用于后端程序解析。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise QwenFilterError(f"qwen request failed: {exc}") from exc
    # LLM输出
    content = completion.choices[0].message.content
    if not content:
        raise QwenFilterError("qwen returned empty content")
    return content


def _parse_selected_indices(content: str, candidate_count: int) -> list[int]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = json.loads(_extract_json_object(content))

    selected = payload.get("selected")
    if not isinstance(selected, list):
        raise QwenFilterError("qwen response must contain a selected list")

    indices: list[int] = []
    seen: set[int] = set()
    for item in selected:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if not isinstance(index, int):
            continue
        if index < 0 or index >= candidate_count or index in seen:
            continue
        seen.add(index)
        indices.append(index)
    return indices


def _extract_json_object(content: str) -> str:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise QwenFilterError("qwen response is not valid JSON")
    return content[start : end + 1]
