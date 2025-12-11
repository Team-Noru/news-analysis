import os
import json
import time
import requests
from utils import to_float_ratio, to_int, parse_date_str
from tqdm import tqdm
from dotenv import load_dotenv
from constants.thresholds import CAP_BUCKET_THRESHOLDS # constants/thresholds 에 CAP_BUCKET_THRESHOLDS 정의
load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

COMPANY_FILE = "company_list_market.json" 
OUTPUT_IPO_FILE = "./output/ipo_dilution_events_mcap.json"
OUTPUT_ALERT_FILE = "./output/ownership_change_alerts_mcap.json"


YEARS = [2025, 2024, 2023]

os.makedirs("./output", exist_ok=True)

def get_cap_bucket(company: dict) -> str:
    mcap_eok = company.get("market_cap_unit_million_krw")
    if mcap_eok is None:
        return "unknown"

    try:
        m = float(mcap_eok)
    except Exception:
        return "unknown"

    if m >= 100_000:    # 10조 이상
        return "mega"
    elif m >= 20_000:   # 2조 이상
        return "large"
    else:
        return "mid_small"


def get_thresholds_for_company(company: dict) -> dict:
    bucket = get_cap_bucket(company)
    return CAP_BUCKET_THRESHOLDS.get(bucket, CAP_BUCKET_THRESHOLDS["unknown"])


# DART API 호출 - 최대주주변동현황 (hyslrChgSttus)
def call_hyslr_change(corp_code: str, year: int):
    url = "https://opendart.fss.or.kr/api/hyslrChgSttus.json"
    params = {
        "crtfc_key": DART_KEY,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": "11011", 
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    
# 한 회사(corp_code)에 대해 최근 N년치 hyslrChgSttus 조회 후 리스트로 반환
def collect_change_events_for_company(company: dict):

    corp_code = company.get("corp_code")
    corp_name = company.get("name")
    all_rows = []

    for year in YEARS:
        data = call_hyslr_change(corp_code, year)
        if data.get("status") != "000":
            continue
        rows = data.get("list", [])
        if not rows:
            continue

        for r in rows:
            change_on_raw = r.get("change_on")
            qota_rt = to_float_ratio(r.get("qota_rt"))
            posesn_stock_co = to_int(r.get("posesn_stock_co"))
            change_cause = r.get("change_cause")
            mxmm_nm = r.get("mxmm_shrholdr_nm")

            all_rows.append(
                {
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "bsns_year": year,
                    "rcept_no": r.get("rcept_no"),
                    "corp_cls": r.get("corp_cls"),
                    "change_on_raw": change_on_raw,
                    "change_on": parse_date_str(change_on_raw),
                    "mxmm_shrholdr_nm": mxmm_nm,
                    "posesn_stock_co": posesn_stock_co,
                    "qota_rt": qota_rt,
                    "change_cause": change_cause,
                    "rm": r.get("rm"),
                    "stlm_dt": r.get("stlm_dt"),
                }
            )

        time.sleep(0.1)  # API 과도호출 방지

    all_rows.sort(key=lambda x: (x["mxmm_shrholdr_nm"] or "", x["change_on"] or ""))
    return all_rows



# IPO 희석 이벤트 탐지
IPO_KEYWORDS = ["상장", "유가증권 상장", "공모", "IPO", "코스닥시장", "신규상장"]


def detect_ipo_dilution(company: dict, events: list):
    """
    최대주주변동현황 목록을 이용해 IPO 시점 지분 희석 이벤트 탐지
    - 같은 최대주주(mxmm_shrholdr_nm)에 대해
      직전 qota_rt → IPO 이벤트 qota_rt 로 떨어진 경우
    """
    results = []
    if not events:
        return results

    mcap_eok = company.get("market_cap_unit_million_krw")
    cap_bucket = get_cap_bucket(company)

    # 최대주주명별 그룹핑 - mxmm_shrholdr_nm 기준
    by_holder = {}
    for e in events:
        key = e.get("mxmm_shrholdr_nm") or "UNKNOWN"
        by_holder.setdefault(key, []).append(e)

    for holder, rows in by_holder.items():
        for i in range(1, len(rows)):
            prev = rows[i - 1]
            curr = rows[i]

            cause = curr.get("change_cause") or ""
            if not any(k in cause for k in IPO_KEYWORDS):
                continue

            prev_ratio = prev.get("qota_rt")
            curr_ratio = curr.get("qota_rt")
            if prev_ratio is None or curr_ratio is None:
                continue
            if prev_ratio <= curr_ratio:
                continue

            dilution_pp = prev_ratio - curr_ratio
            dilution_pct = (dilution_pp / prev_ratio) * 100.0 if prev_ratio != 0 else None

            results.append(
                {
                    "corp_code": company.get("corp_code"),
                    "corp_name": company.get("name"),
                    "market": company.get("market"),
                    "market_cap_unit_eok_krw": mcap_eok, 
                    "cap_bucket": cap_bucket,
                    "holder": holder,
                    "prev_change_on": prev.get("change_on"),
                    "curr_change_on": curr.get("change_on"),
                    "prev_ratio": prev_ratio,
                    "curr_ratio": curr_ratio,
                    "dilution_pp": round(dilution_pp, 4),
                    "dilution_pct": round(dilution_pct, 4) if dilution_pct is not None else None,
                    "change_cause": cause,
                    "stlm_dt": curr.get("stlm_dt"),
                    "rcept_no": curr.get("rcept_no"),
                }
            )

    return results



# 지분 급변(ownership_change) 신호 탐지
def detect_ownership_change(company: dict, events: list):
    """
    최대주주변동현황에서 '지분 급변' 신호 탐지
    - 같은 최대주주(mxmm_shrholdr_nm)에 대해
      직전 대비 qota_rt 변화가 시총 기반 threshold 이상일 때 알림 생성
    """
    results = []
    if not events:
        return results

    thresholds = get_thresholds_for_company(company)
    delta_thr = thresholds["RATIO_DELTA_PPT_THRESHOLD"]
    rel_thr = thresholds["RATIO_REL_CHANGE_PCT_THRESHOLD"]
    min_major = thresholds["MIN_MAJOR_RATIO_FOR_NEW_MAJOR"]

    mcap_eok = company.get("market_cap_unit_million_krw")
    cap_bucket = get_cap_bucket(company)

    by_holder = {}
    for e in events:
        key = e.get("mxmm_shrholdr_nm") or "UNKNOWN"
        by_holder.setdefault(key, []).append(e)

    for holder, rows in by_holder.items():
        if len(rows) < 2:
            continue

        for i in range(1, len(rows)):
            prev = rows[i - 1]
            curr = rows[i]

            prev_ratio = prev.get("qota_rt")
            curr_ratio = curr.get("qota_rt")
            if prev_ratio is None or curr_ratio is None:
                continue

            if max(prev_ratio, curr_ratio) < min_major:
                continue

            delta_pp = curr_ratio - prev_ratio  # +면 지분 증가, -면 감소
            abs_delta_pp = abs(delta_pp)

            # 상대 변화율
            if prev_ratio != 0:
                rel_change_pct = abs_delta_pp / abs(prev_ratio) * 100.0
            else:
                rel_change_pct = 100.0

            if abs_delta_pp >= delta_thr and rel_change_pct >= rel_thr:
                direction = "INCREASE" if delta_pp > 0 else "DECREASE"

                results.append(
                    {
                        "corp_code": company.get("corp_code"),
                        "corp_name": company.get("name"),
                        "market": company.get("market"),
                        "market_cap_unit_eok_krw": mcap_eok,
                        "cap_bucket": cap_bucket,
                        "holder": holder,
                        "direction": direction,
                        "prev_change_on": prev.get("change_on"),
                        "curr_change_on": curr.get("change_on"),
                        "prev_ratio": prev_ratio,
                        "curr_ratio": curr_ratio,
                        "delta_pp": round(delta_pp, 4),
                        "rel_change_pct": round(rel_change_pct, 4),
                        "prev_cause": prev.get("change_cause"),
                        "curr_cause": curr.get("change_cause"),
                        "stlm_dt": curr.get("stlm_dt"),
                        "rcept_no": curr.get("rcept_no"),
                        "thresholds_used": thresholds,
                    }
                )

    return results



def main():
    if not DART_KEY:
        raise RuntimeError("OPEN_DART_API_KEY 가 없음")

    with open(COMPANY_FILE, "r", encoding="utf-8") as f:
        companies = json.load(f)

    ipo_events_all = []
    alerts_all = []

    for comp in tqdm(companies, desc="Collecting & analyzing"):
        corp_code = comp.get("corp_code")
        if not corp_code:
            continue

        # 1) 최대주주변동현황 데이터 수집
        events = collect_change_events_for_company(comp)
        if not events:
            continue

        # 2) IPO 희석 이벤트 탐지
        ipo_events = detect_ipo_dilution(comp, events)
        ipo_events_all.extend(ipo_events)

        # 3) 지분 급변 신호 탐지 (시총 기반 threshold)
        alerts = detect_ownership_change(comp, events)
        alerts_all.extend(alerts)

    # 결과 저장
    with open(OUTPUT_IPO_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": ipo_events_all}, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_ALERT_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": alerts_all}, f, ensure_ascii=False, indent=2)

    print("분석 완료")
    print(f" - IPO 희석 이벤트 수: {len(ipo_events_all)} → {OUTPUT_IPO_FILE}")
    print(f" - 지분 급변 알림 수: {len(alerts_all)} → {OUTPUT_ALERT_FILE}\n")



if __name__ == "__main__":
    main()
