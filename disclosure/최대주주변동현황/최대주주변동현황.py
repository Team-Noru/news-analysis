import os
import json
import time
import requests
from tqdm import tqdm
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

INPUT_CORP_FILE = "corp_merged.json"
RAW_OUTPUT_FILE = "./output/hyslrChgSttus_raw30.json"
EDGE_OUTPUT_FILE = "./output/hyslrChgSttus_edges30.json"

# 시총 순위 30개에 대해서만 데이터 추출
TOP30_NAMES = {
    "삼성전자", "SK하이닉스", "LG에너지솔루션", "삼성바이오로직스", "한화에어로스페이스",
    "KB금융", "현대차", "HD현대중공업", "기아", "셀트리온", "두산에너빌리티",
    "NAVER", "한화오션", "신한지주", "삼성물산", "삼성생명", "카카오",
    "HD한국조선해양", "SK스퀘어", "현대모비스", "하나금융지주", "현대로템",
    "HMM", "POSCO홀딩스", "한국전력", "HD현대일렉트릭", "삼성화재",
    "메리츠금융지주", "LG화학", "우리금융지주",
}

# 최근 3년
CURRENT_YEAR = datetime.now().year  # 2025
YEARS = [CURRENT_YEAR - 1, CURRENT_YEAR - 2, CURRENT_YEAR - 3]  # 2024, 2023, 2022


def call_hyslr_change(corp_code: str, year: int):
    """최대주주변동현황 API 호출"""
    url = "https://opendart.fss.or.kr/api/hyslrChgSttus.json"
    params = {
        "crtfc_key": DART_KEY,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": "11011",  
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        return resp.json()
    except Exception:
        return {"status": "error", "message": "connection or parse error"}


# -------------------------
# 유틸 함수들
# -------------------------
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


def to_float(val):
    if val in ["", "-", None]:
        return None
    try:
        return float(str(val).replace(",", ""))
    except:
        return None


def to_int(val):
    if val in ["", "-", None]:
        return None
    try:
        return int(str(val).replace(",", ""))
    except:
        return None


def normalize_company_id(corp_code: str):
    return f"KR_{corp_code}"


def normalize_shareholder_id(name: str):
    cleaned = clean_name_for_match(name)
    return f"SHR_{cleaned.replace(' ', '')}" if cleaned else "SHR_UNKNOWN"


# -------------------------
# 유효성 검증 함수
# -------------------------
def has_valid_change_row(item: dict) -> bool:
    """
    최대주주명 + 지분율/주식수 중 1개라도 존재하면 유효
    """
    if not item:
        return False

    nm = item.get("mxmm_shrholdr_nm")
    ratio = item.get("qota_rt")
    shares = item.get("posesn_stock_co")

    if nm in ["", None, "-"]:
        return False

    if ratio in ["", None, "-"] and shares in ["", None, "-"]:
        return False

    return True


# -------------------------
# Edge 생성
# -------------------------
def build_change_edge(company: dict, row: dict, year: int, idx: int):
    corp_code = company["corp_code"]
    corp_name = company["name"]

    raw_sh_name = row.get("mxmm_shrholdr_nm") or ""
    sh_name_clean = clean_name_for_match(raw_sh_name)

    company_node_id = normalize_company_id(corp_code)
    shareholder_node_id = normalize_shareholder_id(raw_sh_name)

    after_ratio = to_float(row.get("qota_rt"))
    after_shares = to_int(row.get("posesn_stock_co"))

    edge = {
        "id": f"OWNERSHIP_CHANGE_{corp_code}_{year}_{idx}",
        "type": "OWNERSHIP_CHANGE",
        "source": shareholder_node_id,
        "target": company_node_id,
        "source_name": sh_name_clean or raw_sh_name,
        "target_name": corp_name,
        "properties": {
            "change_date": row.get("change_on"),
            "change_reason": row.get("change_cause"),
            "after_ratio": after_ratio,
            "after_shares": after_shares,
            "bsns_year": year,
            "reprt_code": "11011",
            "rcept_no": row.get("rcept_no"),
        },
    }
    return edge



def main():
    if not DART_KEY:
        raise RuntimeError("OPEN_DART_API_KEY 존재X")

    with open(INPUT_CORP_FILE, "r", encoding="utf-8") as f:
        companies = json.load(f)

    
    target_companies = [c for c in companies if c["name"] in TOP30_NAMES]

    raw_results = []
    edges = []

    os.makedirs("./output", exist_ok=True)

    for comp in tqdm(target_companies):
        corp_code = comp["corp_code"]
        corp_name = comp["name"]

        for year in YEARS:
            resp = call_hyslr_change(corp_code, year)

            if resp.get("status") != "000" or "list" not in resp:
                continue

            rows = resp["list"]
            valid_rows = [r for r in rows if has_valid_change_row(r)]
            if not valid_rows:
                continue

            raw_results.append({
                "corp_code": corp_code,
                "corp_name": corp_name,
                "bsns_year": year,
                "rows": valid_rows,
            })

            for idx, row in enumerate(valid_rows, start=1):
                edges.append(build_change_edge(comp, row, year, idx))

            time.sleep(0.1)

    
    with open(RAW_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": raw_results}, f, ensure_ascii=False, indent=2)

    with open(EDGE_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"edges": edges}, f, ensure_ascii=False, indent=2)

    print("\n 완료!")
    print(f" - Raw items: {len(raw_results)}")
    print(f" - Edge 수: {len(edges)}")
    print(f" - 파일 저장됨: {RAW_OUTPUT_FILE}, {EDGE_OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
