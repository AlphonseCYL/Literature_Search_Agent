from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    raw_payload: str = Field(default="")

    @field_validator("title", "author","platform", "year", "link", "snippet", "raw_payload", mode="before")
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



class Save_Mysql_Info(BaseModel):
    saved_count: int
    received_count: int
    duplicate_count: int
    message: str