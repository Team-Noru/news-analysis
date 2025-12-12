import json
import time
import os
import requests
from dotenv import load_dotenv

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")
PIIC_URL = "https://opendart.fss.or.kr/api/piicDecsn.json"
OUTPUT_PATH = "./output/piic_top100_details.json"

# 중간에 끊기거나 에러가 나도 정상적으로 저장
def save_results_safely(results, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    os.replace(tmp_path, path)

# 유상증자 결정 API 호출 
def fetch_piic_list(corp_code: str, bgn_de: str, end_de: str):
    params = {
        "crtfc_key": DART_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
    }

    try:
        r = requests.get(PIIC_URL, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        print("error")
        return []

    try:
        data = r.json()
    except Exception:
        print(f"JSON 파싱 실패: corp={corp_code}, 기간={bgn_de}~{end_de}")
        return []

    status = data.get("status")
    msg = data.get("message")

    if status == "000":
        return data.get("list", [])

    elif status == "013":
        # 조회건수 0 →
        return []

    else:
        print(f"piicDecsn error {status}: {msg}")
        return []

# dart piicDecsn list를 우리가 쓰기 좋은 형태로 정규화
def normalize_piic_events(piic_list):
    events = []

    for row in piic_list:
        ic_mthn = (row.get("ic_mthn") or "").strip()  # 증자방법 (제3자배정, 주주배정 등)
        third_party = "제3자배정" in ic_mthn

        event = {
            "rcept_no": row.get("rcept_no"),
            "ic_mthn": ic_mthn,
            "isu_de": row.get("isu_de"),          # 발행일
            "isu_knd": row.get("isu_knd"),        # 발행 주식 종류
            "isu_prc": row.get("isu_prc"),        # 발행가
            "isu_qy": row.get("isu_qy"),          # 발행 주식 수
            "evl_bss": row.get("evl_bss"),        # 평가 기준
            "third_party": third_party,           # 제3자배정 여부
            "raw": row,                           # 원본 row 전체
        }
        events.append(event)

    return events


def main():
    results = []
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
            print(f"기존 결과 {len(results)}개 불러옴: {OUTPUT_PATH}")
        except Exception:
            print("기존 파일 읽기 실패")
            results = []

    already_done = {(r["corp_code"], r["year"]) for r in results}

    with open("company_list_market.json", "r", encoding="utf-8") as f:
        companies = json.load(f)

    target_list = companies[:100]

    print(f"총 {len(target_list)}개 기업 처리 시작\n")

    for comp in target_list:
        corp_name = comp.get("name")
        corp_code = comp.get("corp_code")

        if not corp_code:
            continue

        found_any_for_corp = False

        # 2019년부터 2025년까지 유상증자 결정 데이터 조회
        for year in range(2019, 2025 + 1):
            if (corp_code, year) in already_done:
                continue

            bgn_de = f"{year}0101"
            end_de = f"{year}1231"

            piic_list = fetch_piic_list(corp_code, bgn_de, end_de)
            if not piic_list:
                time.sleep(0.2)
                continue

            events = normalize_piic_events(piic_list)
            total_cnt = len(events)
            third_cnt = sum(1 for e in events if e["third_party"])

            if total_cnt >= 1:
                if not found_any_for_corp:
                    print("\n==============================")
                    print(f"{corp_name} ({corp_code})")
                    print("==============================")
                    found_any_for_corp = True

                print(f"- {year}: 전체 {total_cnt}건 (제3자배정 {third_cnt}건)")

                record = {
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "year": year,
                    "total_count": total_cnt,
                    "third_party_count": third_cnt,
                    "events": events,
                }
                results.append(record)
                already_done.add((corp_code, year))

                save_results_safely(results, OUTPUT_PATH)

            time.sleep(0.2)

    print(f"완료! 총 {len(results)}개 (corp_code, year) 결과가 {OUTPUT_PATH}에 저장되었습니다.\n")


if __name__ == "__main__":
    main()
