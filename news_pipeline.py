import asyncio
from typing import Any, Dict
import json
import sys
import re
from pathlib import Path
from context import FakeContext 

# --- ADK Agent Imports ---
from agents.news_type_classifier.agent import (
    news_type_classifier_agent,
    NewsTypeInput,
)
from agents.entity_extractor.agent import (
    entity_extractor_agent,
    EntityExtractorInput,
)
from agents.relation_sentiment.agent import (
    relation_sentiment_agent,
    RelationSentimentInput,
)

async def run_async_agent(agent, context, payload):
    final_output = None
    
    if hasattr(payload, 'model_dump'):
        context.input = payload.model_dump()
    elif isinstance(payload, dict):
        context.input = payload
    else:
        context.input = {"input": str(payload)}

    context.agent = agent 


    try:
        async for event in agent.run_async(context):
            

            if hasattr(event, "output") and event.output is not None:
                final_output = event.output
                break 

            if hasattr(event, "content") and event.content:
                try:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        text_val = event.content.parts[0].text
                    else:
                        text_val = str(event.content)

                    text_val = re.sub(r"```json\s*", "", text_val)
                    text_val = re.sub(r"```", "", text_val)
                    text_val = text_val.strip()

                    data_dict = json.loads(text_val)

                    class DictToObj:
                        def __init__(self, d):
                            for k, v in d.items():
                                if isinstance(v, list):
                                    setattr(self, k, [DictToObj(i) if isinstance(i, dict) else i for i in v])
                                else:
                                    setattr(self, k, v)
                        def model_dump(self):
                            def convert(obj):
                                if isinstance(obj, DictToObj):
                                    return {k: convert(v) for k, v in obj.__dict__.items()}
                                elif isinstance(obj, list):
                                    return [convert(i) for i in obj]
                                else:
                                    return obj
                            return convert(self)

                    final_output = DictToObj(data_dict)
                    
                except Exception as e:
                    pass 

    except Exception as e:
        print(f"[에러] 에이전트 실행 중 예외 발생: {e}")

    return final_output

def run(agent, context, payload):
    return asyncio.run(run_async_agent(agent, context, payload))


# ============================================================
#  뉴스 파이프라인 메인 로직
# ============================================================
def run_news_analysis(article: str) -> Dict[str, Any]:

    context = FakeContext()

    prompt_injected_article = (
        f"--- [분석 대상 뉴스 기사 시작] ---\n"
        f"{article}\n"
        f"--- [분석 대상 뉴스 기사 끝] ---\n"
        f"위 기사 내용을 바탕으로 지시사항을 수행하세요."
    )

    print("뉴스 타입 분류 중...")
    news_type_res = run(
        news_type_classifier_agent,
        context,
        NewsTypeInput(article=prompt_injected_article) 
    )
    
    if news_type_res is None:
        print("[경고] 1단계 실패. 기본값 '기타'로 진행합니다.")
        news_type = "기타"
    else:
        news_type = news_type_res.news_type
    
    print(f"결과: {news_type}")


    print("엔티티 추출 중...")
    entity_res = run(
        entity_extractor_agent,
        context,
        EntityExtractorInput(article=prompt_injected_article)
    )
    
    if entity_res is None:
        print("[경고] 2단계 실패. 빈 리스트로 진행합니다.")
        entities = []
    else:
        entities = entity_res.entities

    print(f"결과: {len(entities)}개 추출됨")


    print("관계 및 감성 분석 중...")
    rel_input = RelationSentimentInput(
        article=prompt_injected_article, 
        news_type=news_type,
        entities=entities,
    )
    final_res = run(relation_sentiment_agent, context, rel_input)
    
    if final_res is None:
        print("[경고] 3단계 실패. 부분 결과만 반환합니다.")
        return {
            "news_type": news_type,
            "entities": [e.model_dump() if hasattr(e, 'model_dump') else e for e in entities],
            "relations": []
        }

    print("완료!")
    return final_res.model_dump()


def load_article_from_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"기사 파일을 찾을 수 없습니다: {p}")
    return p.read_text(encoding="utf-8")

# ============================================================
#  실행
# ============================================================
if __name__ == "__main__":
    default_path = "news1.txt"
    file_path = sys.argv[1] if len(sys.argv) > 1 else default_path
    
    input_path = Path(file_path)
    print(f"[INFO] 분석 시작: {input_path}")

    try:
        article_text = load_article_from_file(file_path)
        result = run_news_analysis(article_text)

        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_filename = input_path.stem + ".json"
        output_path = output_dir / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n[INFO] 결과 저장 완료: {output_path}")
        
        # 화면에 출력
        # print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()