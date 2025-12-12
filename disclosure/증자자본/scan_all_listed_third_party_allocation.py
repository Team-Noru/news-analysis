"""
[PIPELINE #1] 전체 상장사 제3자배정 유상증자 풀 스캔 → 원천 데이터 생성기

- 입력:
  - company_list_market.json (상장사 목록)
- 처리:
  1) piicDecsn(유상증자결정) 연도별 조회
  2) "제3자배정" 이벤트만 필터링
  3) document.xml(zip/xml) 다운로드
  4) ACLASS="THD_ASN_LST" 배정대상자 테이블 파싱 → allocation_tables 생성
- 출력:
  - ./output/capital_increase_third_party_full.json
    (각 이벤트별 배정대상자 테이블이 채워진 원천 데이터)
"""

import os
import io
import json
import time
import zipfile
from typing import List, Dict, Any, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ==========================
#  환경변수 & 상수 설정
# ==========================
load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

if not DART_KEY:
    raise RuntimeError("OPEN_DART_API_KEY 가 .env 에 설정되어 있지 않습니다.")

PIIC_URL = "https://opendart.fss.or.kr/api/piicDecsn.json"
DOC_URL = "https://opendart.fss.or.kr/api/document.xml"

COMPANY_FILE = "company_list_market.json"
OUTPUT_PATH = "./output/capital_increase_third_party_full.json"
# 연도설정
YEARS = list(range(2022, 2025 + 1))
API_SLEEP_SEC = 0.25


# results 리스트를 JSON으로 안전하게 저장
def save_results_safely(results: List[Dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    os.replace(tmp_path, path)


def normalize_text(s: Optional[str]) -> str:
    """공백 / 줄바꿈 정리용"""
    if s is None:
        return ""
    return " ".join(str(s).split())


# piicDecsn 조회
def fetch_piic_list(corp_code: str, bgn_de: str, end_de: str) -> List[Dict[str, Any]]:
    params = {
        "crtfc_key": DART_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
    }

    try:
        r = requests.get(PIIC_URL, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"piicDecsn 요청 실패: corp={corp_code}, 기간={bgn_de}~{end_de}")
        print(f"       이유: {e}")
        return []

    try:
        data = r.json()
    except Exception:
        print(f"JSON 파싱 실패: corp={corp_code}, 기간={bgn_de}~{end_de}")
        print("       raw text (앞 200자):", r.text[:200])
        return []

    status = data.get("status")
    msg = data.get("message")

    if status == "000":
        return data.get("list", []) or []

    elif status == "013":
        # 조회건수 0 → 정상적으로 "없는 것"
        return []

    else:
        print(f"[ERROR] piicDecsn error {status}: {msg}")
        print("URL:", r.url)
        return []


def normalize_piic_events(piic_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    for row in piic_list:
        ic_mthn = (row.get("ic_mthn") or "").strip()
        third_party = "제3자배정" in ic_mthn

        event = {
            # 나중에 document.xml 호출용
            "rcept_no": row.get("rcept_no"),
            # 증자 방법 설명
            "ic_mthn": ic_mthn,
            "isu_de": row.get("isu_de"),      # 발행일 (없으면 None)
            "isu_knd": row.get("isu_knd"),    # 발행 주식 종류
            "isu_prc": row.get("isu_prc"),    # 발행가
            "isu_qy": row.get("isu_qy"),      # 발행 주식 수
            "evl_bss": row.get("evl_bss"),    # 평가 기준
            "third_party": third_party,       # 제3자배정 여부
            "raw": row,                       # 원본 전체
        }
        events.append(event)

    return events


# document.xml 가져오기
def fetch_document_xml(rcept_no: str) -> Optional[str]:
    params = {
        "crtfc_key": DART_KEY,
        "rcept_no": rcept_no,
    }

    try:
        resp = requests.get(DOC_URL, params=params, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[WARN] document.xml 요청 실패: rcept_no={rcept_no}, 이유={e}")
        return None

    raw = resp.content

    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
            xml_candidates = [n for n in names if n.lower().endswith(".xml")]
            if not xml_candidates:
                print(f"[WARN] ZIP 안에 xml 파일 없음: rcept_no={rcept_no}, files={names}")
                return None

            xml_name = xml_candidates[0]
            xml_bytes = z.read(xml_name)

        try:
            xml_text = xml_bytes.decode("euc-kr")
        except UnicodeDecodeError:
            xml_text = xml_bytes.decode("utf-8", errors="ignore")

        return xml_text

    except zipfile.BadZipFile:
        pass

    try:
        txt = raw.decode("euc-kr")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", errors="ignore")

    if "오류가 발생하였습니다" in txt or "접수번호 오류" in txt:
        print(f"document.xml 응답 내 에러 문구 감지: rcept_no={rcept_no}")
        return None

    return txt


# 제3자배정 배정대상자 테이블 파싱
def parse_third_party_allocation(xml_text: str) -> List[Dict[str, Any]]:

    soup = BeautifulSoup(xml_text, "lxml-xml")

    tg = soup.find("TABLE-GROUP", {"ACLASS": "THD_ASN_LST"})
    if tg is None:
        return []

    results: List[Dict[str, Any]] = []

    for tr in tg.find_all("TR"):
        row: Dict[str, Any] = {}

        for cell in tr.find_all(["TE", "TU"]):
            acode = cell.get("ACODE")
            text = normalize_text(cell.text)

            if acode == "PART":
                row["name"] = text
            elif acode == "RLT":
                row["relation"] = text
            elif acode == "SLT_JDG":
                row["reason"] = text
            elif acode == "MNTH":
                row["trade_history"] = text
            elif acode == "ALL_CNT":
                row["assigned_shares"] = text
            elif acode == "ETC":
                row["remark"] = text

        # 의미 없는 행(헤더/합계 등) 제거
        name = row.get("name", "")
        if not name:
            continue
        if name in ("계", "합계"):
            continue

        results.append(row)

    return results


# 메인 파이프라인
def main():
    # 기존 결과 로드
    results: List[Dict[str, Any]] = []
    already_done_rcept: set[str] = set()

    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
            for rec in results:
                rno = rec.get("event", {}).get("rcept_no")
                if rno:
                    already_done_rcept.add(rno)
            print(f"기존 결과 {len(results)}개 불러옴 (이미 처리한 rcept_no {len(already_done_rcept)}개)")
        except Exception:
            print("기존 결과 읽기 실패 → 새로 시작합니다.")
            results = []
            already_done_rcept = set()

    # 회사 리스트 로드
    with open(COMPANY_FILE, "r", encoding="utf-8") as f:
        companies = json.load(f)

    total_corps = len(companies)
    print(f"\n상장사 총 {total_corps}개 대상 (company_list_market.json 기준)\n")

    # 메인 루프
    for idx_c, comp in enumerate(companies, start=1):
        corp_name = comp.get("name")
        corp_code = comp.get("corp_code")

        if not corp_code:
            continue

        print("\n" + "=" * 70)
        print(f"({idx_c}/{total_corps}) {corp_name} ({corp_code})")
        print("=" * 70)

        found_any_for_corp = False

        # 연도별로 piicDecsn 조회
        for year in YEARS:
            bgn_de = f"{year}0101"
            end_de = f"{year}1231"

            piic_list = fetch_piic_list(corp_code, bgn_de, end_de)
            time.sleep(API_SLEEP_SEC)

            if not piic_list:
                continue

            events = normalize_piic_events(piic_list)
            total_cnt = len(events)
            third_events = [e for e in events if e.get("third_party")]
            third_cnt = len(third_events)

            if total_cnt == 0:
                continue

            print(f"  - {year}: 전체 {total_cnt}건 (제3자배정 {third_cnt}건)")

            if third_cnt == 0:
                continue

            found_any_for_corp = True

            # 제3자배정 이벤트별로 document.xml 파싱
            for ev in third_events:
                rcept_no = ev.get("rcept_no")
                if not rcept_no:
                    continue

                if rcept_no in already_done_rcept:
                    continue

                print(f"rcept_no={rcept_no}, 방법={ev.get('ic_mthn')}")
                xml_text = fetch_document_xml(rcept_no)
                time.sleep(API_SLEEP_SEC)

                if not xml_text:
                    print("→ document.xml 없음 / 에러로 스킵")
                    continue

                allocation_tables = parse_third_party_allocation(xml_text)
                print(f"→ 배정대상자 {len(allocation_tables)}명 추출")

                record = {
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                    "year": year,
                    "event": {
                        "rcept_no": rcept_no,
                        "ic_mthn": ev.get("ic_mthn"),
                        "third_party": ev.get("third_party"),
                        "raw_event": ev,  
                    },
                    "allocation_tables": allocation_tables,
                }

                results.append(record)
                already_done_rcept.add(rcept_no)

                # 중간 저장
                save_results_safely(results, OUTPUT_PATH)

        if not found_any_for_corp:
            print("→ 이 회사에서는 제3자배정 건이 발견되지 않았습니다.")

    print(f"\n전체 완료! 제3자배정 이벤트 {len(results)}건이 {OUTPUT_PATH} 에 저장되었습니다.\n")


if __name__ == "__main__":
    main()
