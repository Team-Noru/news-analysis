from pydantic import BaseModel, Field
from typing import List, Optional, Any

class Relation(BaseModel):
    target: str
    relation: str = Field(description="고객사, 공급사, 경쟁사, 관계 불명확 등")
    sentiment: str = Field(description="긍정, 부정, 중립")
    reason: str

class ShortLongImpact(BaseModel):
    단기영향: str
    중장기영향: str

class RiskOpportunity(BaseModel):
    risk: str
    opportunity: str

class EntityAnalysis(BaseModel):
    name: str
    원본문구: str
    상장여부: str = Field(description="상장, 비상장") 
    
    거래소: Optional[str] = None
    sentiment: Optional[str] = None
    
    reason: str
    short_vs_long_term: ShortLongImpact
    risk_opportunity: RiskOpportunity
    relations: List[Relation]

class IndustryCompanyImpact(BaseModel):
    기업명: str
    sentiment: str 
    reason: str

class IndustryImpact(BaseModel):
    industry_name: str
    sentiment: str 
    reason: str
    대표기업영향: List[IndustryCompanyImpact]

class RelationSentimentInput(BaseModel):
    article: str
    news_type: str
    entities: List[Any]

class RelationSentimentOutput(BaseModel):
    entities: List[EntityAnalysis]
    industry_impact: List[IndustryImpact]