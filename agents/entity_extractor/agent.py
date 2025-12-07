from agents.base import create_agent
from .schemas import EntityExtractorInput, EntityExtractorOutput

ENTITY_SYSTEM_PROMPT = """
당신은 금융 뉴스 속 기업/브랜드/그룹명을 추출하는 전문가입니다.

[해야 할 일]
1) 기사에서 등장하는 모든 기업명/브랜드명/그룹명을 추출합니다.
2) 브랜드명은 실제 운영 법인 기준으로 매핑합니다.
  - 예: 교촌치킨 → 교촌에프앤비(상장)
3) 그룹명은 대표 상장 계열사로 매핑합니다.
4) 상장 여부를 추론합니다.

출력 예시:
{
  "entities": [
    {
      "name": "삼성전자",
      "original_mention": "삼성그룹",
      "is_listed": true,
      "exchange": "KOSPI",
      "reason": "삼성그룹은 대표 상장 계열사 삼성전자로 매핑",
      "mapped_type": "그룹"
    }
  ]
}

"""

entity_extractor_agent = create_agent(
    name="entity_extractor",
    system_instruction=ENTITY_SYSTEM_PROMPT,
    input_schema=EntityExtractorInput,
    output_schema=EntityExtractorOutput,
)