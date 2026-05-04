from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
import uuid
import re

class Literature_Metadata_Record(BaseModel):
    """Pydantic template for literature metadata records."""

    model_config = ConfigDict(str_strip_whitespace=True)# 自动去除字符串字段的前后空白

    title: str = Field(default="")
    author: str = Field(default="")
    platform: str = Field(default="")
    year: str = Field(default="")
    link: str = Field(default="")
    snippet: str = Field(default="")
    cited_by: Optional[int] = Field(default=None)
    source: str = Field(default="hiagent")

    @field_validator("title", "author","platform", "year", "link", "snippet", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, value: Any) -> str:
        if value in (None, ""):
            return "db_template_default"
        return str(value)

    @field_validator("cited_by", mode="before")
    @classmethod
    def _normalize_cited_by(cls, value: Any) -> Optional[int]:
        if isinstance(value, dict):
            value = value.get("total")

        if value in (None, ""):
            return None

        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("cited_by must be an integer or null") from exc


class Literature_Metadata_DB(Literature_Metadata_Record):
    """Pydantic template for literature metadata records."""

    model_config = ConfigDict(str_strip_whitespace=True)# 自动去除字符串字段的前后空白

    id: str

    @field_validator("id", mode="before")
    @classmethod
    def _validate_id(cls, value: Any) -> str:
        value_str = str(value).strip()
        # 非空验证
        if not value_str:
            raise ValueError("id 不能为空")
        # 格式验证
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', value):
            raise ValueError("ID必须以字母开头，只能包含字母、数字、下划线和横线")
        # 长度限制
        if len(value) > 50:  # MySQL VARCHAR(50) 常见长度
            raise ValueError("ID长度不能超过50个字符")
        return value_str



class Save_Mysql_Info(BaseModel):
    saved_count: int
    received_count: int
    duplicate_count: int
    message: str