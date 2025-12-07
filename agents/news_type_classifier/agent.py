from agents.base import create_agent
from .schemas import NewsTypeInput, NewsTypeOutput

NEWS_TYPE_SYSTEM_PROMPT = """
당신은 금융 뉴스 전문 분류기입니다.
아래 기사 전문을 보고, 다음 카테고리 중 하나로 분류하세요:

1) 기업실적: 특정 기업의 실적, 매출, 이익, 가이던스, 사업 성과
2) 공시IR: 증자/감자, CB/BW, 신규 수주 공시, 경영진 변경, 상장/상폐 등 공식 공시
3) 산업업황: 특정 산업(반도체, 2차전지, 자동차 등)의 업황, 가격, 수요/공급 전망
4) 정책거시: 금리, 환율, 유가, 물가, 정부/규제 정책, 중앙은행 발표 등 거시 뉴스
5) M&A제휴: 인수합병, 지분투자, JV 설립, 전략적 제휴, 파트너십
6) 사건사고: 리콜, 화재, 보안사고, 품질 이슈, 규제위반, 소송 등 부정 이벤트

JSON 형식으로만 답변합니다:
{
  "news_type": "...",
  "reason": "..."
}
"""

news_type_classifier_agent = create_agent(
    name="news_type_classifier",
    system_instruction=NEWS_TYPE_SYSTEM_PROMPT,
    input_schema=NewsTypeInput,
    output_schema=NewsTypeOutput,
)
