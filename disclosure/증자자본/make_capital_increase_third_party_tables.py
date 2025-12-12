import os
import json
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
PIIC_INPUT_PATH = "./output/piic_top100_details.json"
OUTPUT_PATH = "./output/capital_increase_third_party_tables.json"

# results 리스트를 JSON으로 안전하게 저장
def save_results_safely(results, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    os.replace(tmp_path, path)

# 공백, 줄바꿈 제거
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    return " ".join(str(s).split())


# document.xml 원문 문자열로 반환
def fetch_document_xml(rcept_no: str) -> str | None:
    params = {
        "crtfc_key": DART_KEY,
        "rcept_no": rcept_no,
    }

    try:
        resp = requests.get(DOC_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[WARN] document.xml 요청 실패: rcept_no={rcept_no}, 이유={e}")
        return None

    txt = resp.text
    if "접수번호 오류" in txt or "오류가 발생하였습니다" in txt:
        print(f"document.xml 응답 내 에러 문구 감지: rcept_no={rcept_no}")
        return None

    return txt


#  테이블 파싱
KEYWORDS = ["배정대상자", "청약배정대상", "배정 내역", "배정내역", "배정방법", "배정 방식"]

def extract_candidate_tables(xml_text: str):
    """
    document.xml 에서 '배정대상자' 관련 테이블만 추려서 파싱.
    - 키워드가 포함된 table만 대상으로 함.
    - 각 table을 header / rows 형태로 구조화해서 반환.
    """
    soup = BeautifulSoup(xml_text, "lxml-xml")
    tables = soup.find_all("table")
    parsed_tables = []

    for idx, table in enumerate(tables):
        table_text = " ".join(list(table.stripped_strings))
        if not any(k in table_text for k in KEYWORDS):
            continue

        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            cell_texts = [normalize_text(c.get_text(separator=" ", strip=True)) for c in cells]
            # 완전히 빈 줄은 스킵
            if any(cell_texts):
                rows.append(cell_texts)

        if not rows:
            continue

        header = rows[0]
        body_rows = rows[1:] if len(rows) > 1 else []

        parsed_tables.append(
            {
                "table_index": idx,
                "header": header,
                "rows": body_rows,
                # 디버깅
                "preview_text": table_text[:300],
            }
        )

    return parsed_tables


def main():
    with open(PIIC_INPUT_PATH, "r", encoding="utf-8") as f:
        piic_data = json.load(f)

    results = []
    already_processed_rcept = set()

    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
            for rec in results:
                already_processed_rcept.add(rec["rcept_no"])
            print(f"기존 결과 {len(results)}개 불러옴 (rcept_no {len(already_processed_rcept)}개)")
        except Exception:
            print("기존 결과 읽기 실패 ")
            results = []
            already_processed_rcept = set()

    print("\n제3자배정(third_party=True) 이벤트에 대해 document.xml 파싱 시작\n")

    for corp in piic_data:
        corp_code = corp.get("corp_code")
        corp_name = corp.get("corp_name")

        for ev in corp.get("events", []):
            if not ev.get("third_party"):
                continue  # 제3자배정 아닌 건 스킵

            rcept_no = ev.get("rcept_no")
            ic_mthn = ev.get("ic_mthn")

            if not rcept_no:
                continue

            if rcept_no in already_processed_rcept:
                # 이미 저장된 접수번호면 스킵
                continue

            print(f"{corp_name} ({corp_code}), rcept_no={rcept_no}, 방법={ic_mthn}")

            # 1. document.xml 가져오기
            xml_text = fetch_document_xml(rcept_no)
            if not xml_text:
                print(f"document.xml 없음 / 에러로 스킵")
                time.sleep(0.3)
                continue

            # 2. 배정대상자 관련 테이블 파싱
            tables = extract_candidate_tables(xml_text)
            if not tables:
                print(f"'배정대상자' 관련 테이블 찾지 못함")
            else:
                print(f"후보 테이블 {len(tables)}개 발견")

            # 3. 결과 구조 만들기
            result_rec = {
                "corp_code": corp_code,
                "corp_name": corp_name,
                "year": corp.get("year"),  
                "event": {
                    "rcept_no": rcept_no,
                    "ic_mthn": ic_mthn,
                    "third_party": ev.get("third_party"),
                    "raw_event": ev, 
                },
                "allocation_tables": tables,
            }

            results.append(result_rec)
            already_processed_rcept.add(rcept_no)

            save_results_safely(results, OUTPUT_PATH)

            # DART 호출 너무 빠르게 안 하도록 딜레이
            time.sleep(0.5)

    print(f"\n끝 - 총 {len(results)}개 제3자배정 이벤트에 대한 document.xml 테이블이 {OUTPUT_PATH}에 저장되었습니다.\n")


if __name__ == "__main__":
    main()
