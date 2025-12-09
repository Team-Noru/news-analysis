import os
import json
import time
import requests
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

INPUT_CORP_FILE = "../company/corp_merged.json"
RAW_OUTPUT_FILE = "./output/otr_invest_raw.json"
EDGE_OUTPUT_FILE = "./output/otr_invest_edges.json"

# 조회 연도
YEARS = [2023, 2024, 2025]

def call_dart_invest_api(corp_code: str, year: int):
    """DART 타법인출자 API 호출"""
    url = "https://opendart.fss.or.kr/api/otrCprInvstmntSttus.json"
    params = {
        "crtfc_key": DART_KEY,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": "11011",  # 사업보고서
    }
    resp = requests.get(url, params=params, timeout=10)
    try:
        return resp.json()
    except Exception:
        return {"status": "error", "message": "json parse error"}


def has_valid_data(item: dict) -> bool:
    """
    '-'만 있는 더미 레코드인지 판단.
    꽤 많은 회사가 '합계' / '-'만 있는 행을 반환하므로, 필터링 하였음
    최소한 지분율이나 장부가액이 있는 경우만 '유효'로 봄.
    """
    if not item:
        return False

    if item.get("inv_prm") in ["", "-", None]:
        return False

    # 지분율이나 장부가에 뭔가 값이 있으면 '유효'
    keys_to_check = [
        "bsis_blce_qota_rt",
        "trmend_blce_qota_rt",
        "bsis_blce_acntbk_amount",
        "trmend_blce_acntbk_amount",
    ]

    for k in keys_to_check:
        v = item.get(k)
        if v not in ["", "-", None, "0"]:
            return True

    return False


def convert_amount(amount_str: str):
    """
    '1,234,000' → 1234000 (정수 변환).
    필터링
    """
    if amount_str in ["", "-", None, " "]:
        return None

    s = str(amount_str).strip()

    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    s = s.replace(",", "")

    if s.startswith(("+", "-")):
        if s[0] == "-":
            is_negative = True
        s = s[1:].strip()
        
    if not s.isdigit():
        return None

    val = int(s)
    return -val if is_negative else val


def normalize_company_id(corp_code: str) -> str:
    """그래프 노드 ID: KR_ + corp_code 형태로 생성"""
    return f"KR_{corp_code}"


def clean_name_for_match(name: str) -> str:
    """매칭용 회사명 정규화: (주) 제외 """
    if not name:
        return ""
    cleaned = (
        name.replace("㈜", "")
        .replace("(주)", "")
        .replace("주식회사", "")
        .strip()
    )
    return cleaned


# -------------------------------

def build_edge(
    investor: dict,
    investee_code: str | None,
    investee_name_resolved: str | None,
    row: dict,
    year: int,
    index: int,
):
    """
    그래프용 출자 관계 edge 생성
    investor: corp_merged.json 에서 온 회사 dict (name, corp_code 등)
    investee_code: 매칭된 피투자사 corp_code (없으면 None)
    investee_name_resolved: 매칭된 피투자사 이름 (없으면 None)
    """
    investor_id = normalize_company_id(investor["corp_code"])

    if investee_code:
        target_id = normalize_company_id(investee_code)
        target_name = investee_name_resolved
    else:
        # DART에 있으나 corp_merged.json에 없는 케이스
        raw_name = row.get("inv_prm", "")
        target_id = f"UNRESOLVED_{raw_name}"
        target_name = investee_name_resolved or raw_name

    # 숫자 변환 (지분율)
    try:
        stake_ratio = (
            float(row["trmend_blce_qota_rt"])
            if row.get("trmend_blce_qota_rt") not in ["", "-", None]
            else None
        )
    except (ValueError, TypeError):
        stake_ratio = None

    edge = {
        "id": f"INV_{investor_id}_{year}_{index}",
        "type": "INVESTOR_INVESTEE",
        "source": investor_id,
        "target": target_id,
        "source_name": investor.get("name"),
        "target_name": target_name,
        "properties": {
            "stake_ratio": stake_ratio,
            "book_value": convert_amount(row.get("trmend_blce_acntbk_amount")),
            "first_acq_date": row.get("frst_acqs_de"),
            "purpose": row.get("invstmnt_purps"),
            "acq_amount": convert_amount(row.get("frst_acqs_amount")),
            "investee_name_raw": row.get("inv_prm"),
            "as_of": row.get("stlm_dt"),
            "bsns_year": year,
            "rcept_no": row.get("rcept_no"),
        },
    }
    return edge



# -------------------------------

def main():
    if not DART_KEY:
        raise RuntimeError("OPEN_DART_API_KEY 가 없음.")

    with open(INPUT_CORP_FILE, "r", encoding="utf-8") as f:
        companies = json.load(f)

    # json 기업 이름 매칭
    corp_name_to_code: dict[str, str] = {}
    for c in companies:
        name_clean = clean_name_for_match(c["name"])
        if name_clean:
            corp_name_to_code[name_clean] = c["corp_code"]

    raw_results = []  # 원본 구조를 모으는 리스트
    edges = []        # 그래프 edge 리스트

    os.makedirs("./output", exist_ok=True)

    print("\n전체 기업에 대해 2023~2025 타법인출자 관계 수집\n")

    for comp in tqdm(companies):
        investor_code = comp["corp_code"]
        investor_name = comp["name"]

        for year in YEARS:
            try:
                # DART API 호출
                resp = call_dart_invest_api(investor_code, year)

                if resp.get("status") != "000" or "list" not in resp:
                    # 에러 또는 데이터 없음
                    continue

                rows = resp["list"]
                valid_rows = [r for r in rows if has_valid_data(r)]

                if not valid_rows:
                    continue


                raw_results.append(
                    {
                        "corp_code": investor_code,
                        "corp_name": investor_name,
                        "bsns_year": year,
                        "reprt_code": "11011",
                        "rows": valid_rows,
                    }
                )

                
                for idx, row in enumerate(valid_rows, start=1):
                    raw_investee_name = row.get("inv_prm", "")
                    investee_clean = clean_name_for_match(raw_investee_name)
                    investee_code = corp_name_to_code.get(investee_clean)

                    edge = build_edge(
                        investor=comp,
                        investee_code=investee_code,
                        investee_name_resolved=investee_clean if investee_clean else None,
                        row=row,
                        year=year,
                        index=idx,
                    )
                    edges.append(edge)

                # 과도한 호출 방지용 딜레이 
                time.sleep(0.1)

            except Exception as e:
                print(f"ERROR: {investor_name}({investor_code}) {year}년 처리 중 오류 → {e}")
                continue

    # -------------------------------
    # 결과 저장
    with open(RAW_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": raw_results}, f, ensure_ascii=False, indent=2)

    with open(EDGE_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"edges": edges}, f, ensure_ascii=False, indent=2)

    print("\n완료!")
    print(f" - 유효 출자 원본 JSON: {len(raw_results)}개 회사/연도 → {RAW_OUTPUT_FILE}")
    print(f" - 그래프 edge 개수: {len(edges)} → {EDGE_OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
