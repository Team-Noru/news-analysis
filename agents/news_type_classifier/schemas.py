from pydantic import BaseModel
from typing import Literal

class NewsTypeInput(BaseModel):
    article: str

class NewsTypeOutput(BaseModel):
    news_type: Literal[
        "기업실적",
        "공시IR",
        "산업업황",
        "정책거시",
        "M&A제휴",
        "사건사고"
    ]
    reason: str
