import json
import os
from typing import Any, Dict, List

INPUT_PATH = "./output/capital_increase_third_party_full.json"
OUTPUT_PATH = "./output/capital_increase_edges_clean.json"


# 텍스트 유틸
def norm(s: Any) -> str:
    if s is None:
        return ""
    return " ".join(str(s).split()).strip()


def is_hangul_name_like(text: str) -> bool:
    """
    아주 러프하게 '개인 이름 같아 보이는 문자열' 필터
    - 공백 없음
    - 길이 2~3
    - 대부분이 한글
    """
    t = norm(text)
    if not t:
        return False
    # 괄호/숫자/기호 날리기
    for ch in "().,·-1234567890":
        t = t.replace(ch, "")
    t = t.strip()

    if len(t) < 2 or len(t) > 3:
        return False

    # 한글 비율 체크
    hangul_cnt = sum(1 for c in t if "가" <= c <= "힣")
    return hangul_cnt >= len(t) * 0.8  # 거의 다 한글이면


# 필터 룰
CORP_KEYWORDS = [
    "주식회사",
    "㈜",
    "유한회사",
    "은행",
    "증권",
    "보험",
    "자산운용",
    "캐피탈",
    "투자조합",
    "신기술투자조합",
    "벤처",
    "파트너스",
    "PEF",
    "사모투자",
]

TRUSTEE_KEYWORDS = [
    "신탁업자 지위에서",
    "신탁업자의 지위에서",
    "신탁업자 지위로",
    "집합투자업자",
    "수탁자",
]

RELATION_KEEP_KEYWORDS = [
    "최대주주",
    "주요주주",
    "계열회사",
    "관계회사",
    "관계기업",
    "자회사",
    "종속회사",
    "특수관계",
    "전략적",
    "업무",
    "자본제휴",
]

RELATION_NOISE_EXACT = [
    "-",
    "없음",
    "해당 없음",
    "해당사항 없음",
    "해당사항없음",
    "해당사항 없음(주1)",
    "해당사항없음.",
    "개인",
    "직원",
    "임원",
    "우리사주조합",
    "소속근로자",
]

REMARK_BOOST_KEYWORDS = [
    "의무보유",
    "전환우선주",
    "콜옵션",
    "풋옵션",
    "지분 인수",
    "전략적",
    "M&A",
    "경영권",
    "지배력",
]


def contains_any(text: str, keywords: List[str]) -> bool:
    t = norm(text)
    return any(k in t for k in keywords)


def is_sum_row(name: str) -> bool:
    # "계" 같은 합계 행
    t = norm(name)
    return t in ["계", "합계"]


def is_trustee_like(name: str) -> bool:
    return contains_any(name, TRUSTEE_KEYWORDS)


def is_corporate_or_fund(name: str) -> bool:
    return contains_any(name, CORP_KEYWORDS)


def is_relation_noise(relation: str) -> bool:
    t = norm(relation)
    return t in RELATION_NOISE_EXACT


def is_relation_interesting(relation: str) -> bool:
    return contains_any(relation, RELATION_KEEP_KEYWORDS)


def is_remark_or_reason_interesting(remark: str, reason: str) -> bool:
    text = f"{norm(remark)} {norm(reason)}"
    return contains_any(text, REMARK_BOOST_KEYWORDS)


def should_keep_row(row: Dict[str, Any]) -> bool:
    """
    배정대상자 row를 그래프 엣지로 쓸지 말지 결정
    """
    name = norm(row.get("name"))
    relation = norm(row.get("relation"))
    reason = norm(row.get("reason"))
    remark = norm(row.get("remark"))

    if not name:
        return False

    # 1) 합계 행 제거
    if is_sum_row(name):
        return False

    # 2) 신탁업자/집합투자업자 역할만 하는 경우 → 일단 노이즈로 처리
    if is_trustee_like(name):
        return False

    # 3) 개인 이름처럼 보이고, relation도 노이즈 계열이면 버림
    if is_hangul_name_like(name) and is_relation_noise(relation):
        return False

    # 4) 기업/펀드 키워드가 들어가면 그냥 keep
    if is_corporate_or_fund(name):
        return True

    # 5) relation이 흥미로운 관계면 keep
    if is_relation_interesting(relation):
        return True

    # 6) remark/reason에 의무보유/전환우선주 등 기재되어 있으면 keep
    if is_remark_or_reason_interesting(remark, reason):
        return True

    # 그 외는 일단 버린다 
    return False


def parse_int_or_none(s: Any) -> int | None:
    t = norm(s)
    if not t or t in ["-", "해당없음", "해당 없음"]:
        return None
    try:
        return int(t.replace(",", ""))
    except ValueError:
        return None


# 메인 파이프라인
def main():
    if not os.path.exists(INPUT_PATH):
        print(f"입력 파일을 찾을 수 없습니다: {INPUT_PATH}")
        return

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    edges: List[Dict[str, Any]] = []

    print(f"입력 이벤트 개수: {len(data)}")

    for rec in data:
        corp_code = rec.get("corp_code")
        corp_name = rec.get("corp_name")
        year = rec.get("year")
        event = rec.get("event") or {}
        rcept_no = event.get("rcept_no")

        tables = rec.get("allocation_tables") or []
        if not tables:
            continue

        for row in tables:
            if not should_keep_row(row):
                continue

            name = norm(row.get("name"))

            edge = {
                "source_name": name,                 # 투자자 이름 (기업/펀드/기관/의미 있는 개인)
                "target_corp_code": corp_code,       # 발행사
                "target_corp_name": corp_name,
                "relation_type": "CAPITAL_INCREASE_PARTICIPATION",
                "meta": {
                    "year": year,
                    "rcept_no": rcept_no,
                    "assigned_shares": parse_int_or_none(row.get("assigned_shares")),
                    "assigned_shares_raw": norm(row.get("assigned_shares")),
                    "relation_raw": norm(row.get("relation")),
                    "reason": norm(row.get("reason")),
                    "trade_history": norm(row.get("trade_history")),
                    "remark": norm(row.get("remark")),
                },
            }

            edges.append(edge)

    # 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(edges, f, ensure_ascii=False, indent=2)

    print(f"완료! 최종 엣지 {len(edges)}개를 {OUTPUT_PATH} 에 저장했습니다.")


if __name__ == "__main__":
    main()
