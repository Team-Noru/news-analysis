import os
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Tuple

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPEN_DART_API_KEY")
BASE_URL = "https://opendart.fss.or.kr/api/otrCprInvstmntSttus.json"

MAX_COMPANIES = None  # 200 이런 식으로 제한해도 됨

# 사업연도 / 보고서 코드
BSNS_YEAR = "2023"       
REPRT_CODE = "11011"      # 11011 = 사업보고서


def load_corp_list(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = []
    for item in data:
        corp_code = item.get("corp_code")
        name = item.get("name")
        if corp_code and corp_code.strip():
            result.append((corp_code.strip(), name or ""))

    seen = set()
    deduped = []
    for corp_code, name in result:
        if corp_code not in seen:
            seen.add(corp_code)
            deduped.append((corp_code, name))
    return deduped


def call_otr_api(corp_code: str, bsns_year: str, reprt_code: str) -> Dict[str, Any]:
    """
    타법인 출자현황 API 호출
    """
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
    }
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def extract_valid_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    - status=000
    - list 안에서 inv_prm이 '-'나 '합계'가 아니고
    - 지분율/금액이 전부 '-'가 아닌 row만 필터링
    """
    if data.get("status") != "000":
        return []

    rows = data.get("list") or []
    valid = []

    for item in rows:
        inv_prm = item.get("inv_prm")  # 피투자회사명
        qota_rt = item.get("trmend_blce_qota_rt")  # 기말 지분율
        amount = item.get("trmend_blce_acntbk_amount")  # 기말 장부가액

        if inv_prm in ("-", "합계") or not inv_prm:
            continue
        if (qota_rt in ("-", None, "")) and (amount in ("-", None, "")):
            continue

        valid.append(item)

    return valid


def main():
    if not API_KEY:
        raise RuntimeError("OPEN_DART_API_KEY 가 없음.")

    corp_path = "corp_merged.json"  
    corps = load_corp_list(corp_path)

    total_corps = len(corps)
    print(f"총 corp_code 개수: {total_corps}")
    if MAX_COMPANIES is not None:
        print(f"테스트 대상 상한: {MAX_COMPANIES}개 (실제: {min(total_corps, MAX_COMPANIES)}개)")

    results = []  # 결과 데이터 
    tested = 0
    hit_count = 0

    for corp_code, name in corps:
        if MAX_COMPANIES is not None and tested >= MAX_COMPANIES:
            break

        tested += 1
        try:
            data = call_otr_api(corp_code, BSNS_YEAR, REPRT_CODE)
        except Exception as e:
            print(f"[ERROR] {name}({corp_code}) 호출 실패: {e}")
            continue

        valid_rows = extract_valid_rows(data)

        if valid_rows:
            hit_count += 1
            print(
                f"[HIT] {name}({corp_code}) - 유효 출자 row {len(valid_rows)}개"
            )
        
            results.append(
                {
                    "corp_code": corp_code,
                    "corp_name": name,
                    "bsns_year": BSNS_YEAR,
                    "reprt_code": REPRT_CODE,
                    "rows": valid_rows,
                }
            )
        else:
            print(f"[EMPTY] {name}({corp_code}) - 유효 출자 데이터 없음")

        # 너무 빠르게 호출하지 않도록 살짝 딜레이 
        time.sleep(0.2)

    # output 디렉토리 생성
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    out_path = out_dir / "타법인출자현황.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n=== 요약 ===")
    print(f"- 테스트한 회사 수: {tested}")
    print(f"- 실제 출자 데이터가 존재하는 회사 수: {hit_count}")
    print(f"- 결과 파일: {out_path.resolve()}")


if __name__ == "__main__":
    main()
