from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

class Save_To_Redis_Info(BaseModel):
    saved_cnt: int
    received_cnt: int
    duplicate_cnt: int
    message: str