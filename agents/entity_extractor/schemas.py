from pydantic import BaseModel, Field 
from typing import List, Optional 

class Entity(BaseModel):
    name: str
    original_mention: str
    is_listed: bool
    exchange: Optional[str] = Field(description="KOSPI, KOSDAQ, NYSE, NASDAQ, 기타 등", default=None)
    reason: str
    mapped_type: str = Field(description="개별기업, 브랜드, 그룹 중 하나")

class EntityExtractorInput(BaseModel):
    article: str

class EntityExtractorOutput(BaseModel):
    entities: List[Entity]