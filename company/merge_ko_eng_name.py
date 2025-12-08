import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# 파일 경로는 네 환경에 맞게 수정해줘
LISTED_JSON_PATH = Path("listed_companies_korea.json")
DART_JSON_PATH = Path("dart_corp_code.json")
OUTPUT_JSON_PATH = Path("corp_merged.json")
UNMATCHED_JSON_PATH = Path("corp_unmatched.json")


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_dart_index(dart_list: List[Dict[str, Any]]):
    """
    dart_corp_code.json 을 빠르게 검색할 수 있도록 index 생성
    - name_index: corp_name(strip 기준) → [rows...]
    - stock_index: stock_code → [rows...]
    """
    name_index: Dict[str, List[Dict[str, Any]]] = {}
    stock_index: Dict[str, List[Dict[str, Any]]] = {}

    for row in dart_list:
        name = (row.get("corp_name") or "").strip()
        if name:
            name_index.setdefault(name, []).append(row)

        stock = (row.get("stock_code") or "").strip()
        if stock:
            stock_index.setdefault(stock, []).append(row)

    return name_index, stock_index


def find_dart_record(
    company: Dict[str, Any],
    name_index: Dict[str, List[Dict[str, Any]]],
    stock_index: Dict[str, List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """
    1순위: corp_name == company["name"] 로 매칭
    2순위: stock_code == ticker (숫자 6자리인 경우만)
    여러 개 나오면 그냥 첫 번째 사용
    """
    name = (company.get("name") or "").strip()
    ticker = (company.get("ticker") or "").strip()

    # 1) 이름으로 매칭
    if name in name_index:
        candidates = name_index[name]
        if len(candidates) == 1:
            return candidates[0]
        else:
            # 같은 이름이 여러 개라면, ticker(숫자)로 한 번 더 거르기
            numeric_ticker = "".join(ch for ch in ticker if ch.isdigit())
            if len(numeric_ticker) == 6:
                filtered = [
                    r for r in candidates
                    if (r.get("stock_code") or "").strip() == numeric_ticker
                ]
                if filtered:
                    return filtered[0]
            # 그래도 여러 개면 일단 첫 번째
            return candidates[0]

    # 2) 이름으로 못 찾았으면, ticker가 순수 숫자 6자리인 경우 stock_code로 시도
    numeric_ticker = "".join(ch for ch in ticker if ch.isdigit())
    if len(numeric_ticker) == 6 and numeric_ticker in stock_index:
        candidates = stock_index[numeric_ticker]
        if len(candidates) == 1:
            return candidates[0]
        # 여러 개면 그냥 첫 번째
        return candidates[0]

    # 아무 것도 못 찾은 경우
    return None


def main():
    print("[INFO] JSON 로딩 중...")
    listed_companies = load_json(LISTED_JSON_PATH)
    dart_data = load_json(DART_JSON_PATH)

    print(f"[INFO] 상장사 개수: {len(listed_companies)}")
    print(f"[INFO] DART 전체 기업 개수: {len(dart_data)}")

    name_index, stock_index = build_dart_index(dart_data)

    merged: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []

    for comp in listed_companies:
        dart_row = find_dart_record(comp, name_index, stock_index)

        if dart_row is None:
            unmatched.append(comp)
            continue

        # listed 레코드 + dart 필드 3개 병합
        merged_record = {
            **comp,
            "corp_code": dart_row.get("corp_code"),
            "corp_eng_name": dart_row.get("corp_eng_name"),
            "dart_stock_code": dart_row.get("stock_code"),
            "dart_modify_date": dart_row.get("modify_date"),
        }
        merged.append(merged_record)

    # 결과 저장
    with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    with UNMATCHED_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(unmatched, f, ensure_ascii=False, indent=2)

    print(f"[INFO] 매칭 성공: {len(merged)}개 → {OUTPUT_JSON_PATH}")
    print(f"[INFO] 매칭 실패: {len(unmatched)}개 → {UNMATCHED_JSON_PATH}")


if __name__ == "__main__":
    main()
