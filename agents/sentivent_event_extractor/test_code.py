import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from context import FakeContext
from agents.sentivent_event_extractor.agent import sentivent_event_agent
from agents.sentivent_event_extractor.schemas import EventExtractionInput, EventExtractionOutput
import json

async def test_sentivent(article_path: str):
    with open(article_path, "r", encoding="utf-8") as f:
        article = f.read()

    # print(article)
    context = FakeContext()
    context.input = EventExtractionInput(article=article)
    context.agent = sentivent_event_agent

    async for event in sentivent_event_agent.run_async(context):
        if getattr(event, "type", None) == "FINAL":
            return event.data
        
        # Content 응답도 파싱 시도
        if getattr(event, "content", None):
            try:
                raw_text = event.content.parts[0].text
                parsed = json.loads(raw_text)
                return parsed
            except Exception as e:
                print("JSON 파싱 오류:", e)
                print("원문:\n", raw_text)

    return None



    if final_output:
        print(final_output.model_dump_json(indent=2))
    else:
        print("결과 없음")

if __name__ == "__main__":
    article_path = "news2.txt"
    result = asyncio.run(test_sentivent(article_path))
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("결과 없음")