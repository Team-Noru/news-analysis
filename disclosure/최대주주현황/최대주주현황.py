import os
import json
import time
import requests
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

INPUT_CORP_FILE = "corp_merged.json"
RAW_OUTPUT_FILE = "./output/hyslrSttus_raw.json"
EDGE_OUTPUT_FILE = "./output/hyslrSttus_edges.json"

YEARS = [2025]

# -----------------------------
# 공통 유틸
# -----------------------------
def call_hyslr_status(corp_code: str, year: int):
    """
    최대주주현황 API 호출 (/api/hyslrSttus.json)
    """
    url = "https://opendart.fss.or.kr/api/hyslrSttus.json"
    params = {
        "crtfc_key": DART_KEY,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": "11011",  
    }
    resp = requests.get(url, params=params, timeout=10)
    try:
        return resp.json()
    except Exception:
        return {"status": "error", "message": "json parse error"}


def to_float(val):
    if val in ["", "-", None, " "]:
        return None
    s = str(val).strip()

    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    s = s.replace(",", "")

    if s.startswith(("+", "-")):
        if s[0] == "-":
            is_negative = True
        s = s[1:].strip()

    try:
        num = float(s)
    except ValueError:
        return None

    return -num if is_negative else num


def to_int(val):
    if val in ["", "-", None, " "]:
        return None
    s = str(val).strip()

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

    num = int(s)
    return -num if is_negative else num


def clean_name_for_match(name: str) -> str:
    if not name:
        return ""
    cleaned = (
        name.replace("㈜", "")
        .replace("(주)", "")
        .replace("주식회사", "")
        .replace(" 외 ", " ")
        .replace("외 ", "")
        .replace(" 등", "")
        .strip()
    )
    return cleaned


def normalize_company_id(corp_code: str) -> str:
    return f"KR_{corp_code}"


def normalize_shareholder_id(name: str) -> str:
    cleaned = clean_name_for_match(name)
    return f"SHR_{cleaned.replace(' ', '')}" if cleaned else "SHR_UNKNOWN"


def has_valid_hyslr_row(item: dict) -> bool:
    """
    최대주주현황 row가 의미 있는지 판단 (명세서 기준 필드 사용):

    - nm (성명)이 없으면 무시
    - 기초/기말 주식수 & 지분율이 모두 '-' or 공백이면 무시
    """
    if not item:
        return False

    nm = item.get("nm")
    if nm in ["", "-", None]:
        return False

    if nm == "계":
        return False

    ratio_begin = item.get("bsis_posesn_stock_qota_rt")
    ratio_end = item.get("trmend_posesn_stock_qota_rt")
    shares_begin = item.get("bsis_posesn_stock_co")   
    shares_end = item.get("trmend_posesn_stock_co")   

    if (
        ratio_begin in ["", "-", None]
        and ratio_end in ["", "-", None]
        and shares_begin in ["", "-", None]
        and shares_end in ["", "-", None]
    ):
        return False

    return True


# -----------------------------
# Edge 빌더
# -----------------------------
def build_hyslr_edge(company: dict, row: dict, year: int, idx: int):
    """
    최대주주/특수관계인 관계를 그래프 Edge로 변환 (명세서 기준):

    list 내 필드:
    - nm: 성명 (주주)
    - relate: 관계 (최대주주, 최대주주 본인, 특수관계인 등)
    - stock_knd: 주식 종류
    - bsis_posesn_stock_co / bsis_posesn_stock_qota_rt: 기초
    - trmend_posesn_stock_co / trmend_posesn_stock_qota_rt: 기말
    - stlm_dt: 결산 기준일
    """
    corp_code = company["corp_code"]
    corp_name = company["name"]

    raw_name = row.get("nm") or ""
    relate = row.get("relate")  
    stock_kind = row.get("stock_knd")

    name_clean = clean_name_for_match(raw_name)
    sh_node_id = normalize_shareholder_id(raw_name)
    company_node_id = normalize_company_id(corp_code)

    # Edge type 분기 (relate 필드 기준)
    edge_type = "RELATED_PARTY"
    if relate and "최대주주" in relate:
        edge_type = "MAJOR_SHAREHOLDER"
    elif relate and "특수관계인" in relate:
        edge_type = "RELATED_PARTY"

    ratio_begin_str = row.get("bsis_posesn_stock_qota_rt")
    ratio_end_str = row.get("trmend_posesn_stock_qota_rt")
    shares_begin_str = row.get("bsis_posesn_stock_co")
    shares_end_str = row.get("trmend_posesn_stock_co")

    ratio_begin = to_float(ratio_begin_str)
    ratio_end = to_float(ratio_end_str)
    shares_begin = to_int(shares_begin_str)
    shares_end = to_int(shares_end_str)

    ratio_delta = (
        ratio_end - ratio_begin
        if ratio_begin is not None and ratio_end is not None
        else None
    )
    shares_delta = (
        shares_end - shares_begin
        if shares_begin is not None and shares_end is not None
        else None
    )

    edge = {
        "id": f"{edge_type}_KR_{corp_code}_{year}_{idx}",
        "type": edge_type,
        "source": sh_node_id,
        "target": company_node_id,
        "source_name": name_clean or raw_name,
        "target_name": corp_name,
        "properties": {
            "relation_se": relate,          # 관계 (최대주주, 특수관계인 등)
            "relation_desc": relate,        # 필요시 동일 값
            "stock_kind": stock_kind,       # 보통주 등
            "ratio_begin": ratio_begin,     # 기초 지분율
            "ratio_end": ratio_end,         # 기말 지분율
            "ratio_delta": ratio_delta,     # 지분율 변화
            "shares_begin": shares_begin,   # 기초 주식수
            "shares_end": shares_end,       # 기말 주식수
            "shares_delta": shares_delta,   # 주식수 변화
            "as_of": row.get("stlm_dt"),    # 결산 기준일 (YYYY-MM-DD)
            "bsns_year": year,              # 사업연도
            "reprt_code": row.get("reprt_code") or "11011",
            "rcept_no": row.get("rcept_no"),
            "corp_cls": row.get("corp_cls"),
            "rm": row.get("rm"),            # 비고
        },
    }
    return edge



def main():
    if not DART_KEY:
        raise RuntimeError("OPEN_DART_API_KEY 존재X")

    with open(INPUT_CORP_FILE, "r", encoding="utf-8") as f:
        companies = json.load(f)

    raw_results = []
    edges = []

    os.makedirs("./output", exist_ok=True)


    for comp in tqdm(companies):
        corp_code = comp["corp_code"]
        corp_name = comp["name"]

        for year in YEARS:
            try:
                resp = call_hyslr_status(corp_code, year)

    
                if resp.get("status") != "000" or "list" not in resp:
                    continue

                rows = resp["list"]
                valid_rows = [r for r in rows if has_valid_hyslr_row(r)]

                if not valid_rows:
                    continue

                raw_results.append(
                    {
                        "corp_code": corp_code,
                        "corp_name": corp_name,
                        "bsns_year": year,
                        "reprt_code": "11011",
                        "rows": valid_rows,
                    }
                )

                for idx, row in enumerate(valid_rows, start=1):
                    edge = build_hyslr_edge(comp, row, year, idx)
                    edges.append(edge)

                time.sleep(0.1)

            except Exception as e:
                print(f"[ERROR] {corp_name}({corp_code}) {year}년 처리 중 오류: {e}")
                continue

    with open(RAW_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": raw_results}, f, ensure_ascii=False, indent=2)

    with open(EDGE_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"edges": edges}, f, ensure_ascii=False, indent=2)

    print("\n hyslrSttus 처리 완료")
    print(f" - 유효 원본 회사/연도 수: {len(raw_results)} → {RAW_OUTPUT_FILE}")
    print(f" - 그래프 edge 개수: {len(edges)} → {EDGE_OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
