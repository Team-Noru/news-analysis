"""
[PIPELINE #2] (단순 버전) 제3자배정 이벤트 목록 → allocation_tables 채우기

- 목적:
  이미 수집된 제3자배정 이벤트(JSON)에 대해 document.xml을 재조회하여
  배정대상자(THD_ASN_LST) 테이블을 allocation_tables로 채운다.

- 입력:
  - ./output/capital_increase_third_party_tables.json
    (제3자배정 이벤트 메타만 있는 상태 / 또는 후보 테이블만 있는 상태)

- 처리:
  1) rcept_no로 document.xml 다운로드
  2) ACLASS="THD_ASN_LST" 파싱 → allocation_tables 생성

- 출력:
  - ./output/capital_increase_third_party_table_with_alloc.json
"""

import os
import io
import json
import time
import zipfile
import requests
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
INPUT_FILE = "./output/capital_increase_third_party_tables.json"
OUTPUT_FILE = "./output/capital_increase_third_party_table_with_alloc.json"


# ---------------------------
# 1) document.xml 가져오기 (ZIP → XML)
# ---------------------------
def fetch_document_xml(rcept_no: str) -> Optional[str]:
    """
    document.xml API 호출 후:
    1) resp.content를 ZIP으로 먼저 시도
    2) BadZipFile이면 일반 텍스트(euc-kr → utf-8)로 디코딩 시도
    """
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

    # 1) ZIP 우선 시도
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
        # ZIP 아니면 일반 텍스트로
        pass

    # 2) 일반 텍스트 디코딩
    try:
        txt = raw.decode("euc-kr")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", errors="ignore")

    if "오류가 발생하였습니다" in txt or "접수번호 오류" in txt:
        print(f"[WARN] document.xml 응답 내 에러 문구 감지: rcept_no={rcept_no}")
        return None

    return txt


# ---------------------------
# 2) XML에서 제3자배정 '배정대상자 테이블' 파싱
# ---------------------------
def parse_third_party_allocation(xml_text: str) -> List[Dict[str, Any]]:
    """
    document.xml 안에서 ACLASS="THD_ASN_LST" 인 TABLE-GROUP을 찾아
    제3자배정 '배정대상자' 테이블 파싱
    """
    soup = BeautifulSoup(xml_text, "lxml-xml")

    tg = soup.find("TABLE-GROUP", {"ACLASS": "THD_ASN_LST"})
    if tg is None:
        return []

    results: List[Dict[str, Any]] = []

    for tr in tg.find_all("TR"):
        row: Dict[str, Any] = {}

        for cell in tr.find_all(["TE", "TU"]):
            acode = cell.get("ACODE")
            text = (cell.text or "").strip()

            if acode == "PART":
                row["name"] = text                 # 배정 대상자 명
            elif acode == "RLT":
                row["relation"] = text             # 관계
            elif acode == "SLT_JDG":
                row["reason"] = text               # 선정 경위
            elif acode == "MNTH":
                row["trade_history"] = text        # 6개월 내 거래내역
            elif acode == "ALL_CNT":
                row["assigned_shares"] = text      # 배정 주식수
            elif acode == "ETC":
                row["remark"] = text               # 비고

        if "name" in row:
            results.append(row)

    return results


# ---------------------------
# 3) 기존 JSON을 읽어서 allocation_tables 채우기
# ---------------------------
def run_fill_allocation_tables():
    # 1) 입력 JSON 로드
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"입력 이벤트 개수: {len(data)}\n")

    updated: List[Dict[str, Any]] = []

    for idx, item in enumerate(data, start=1):
        corp_code = item.get("corp_code")
        corp_name = item.get("corp_name")
        year = item.get("year")
        event = item.get("event") or {}
        rcept_no = event.get("rcept_no")

        print("=" * 60)
        print(f"({idx}/{len(data)}) {corp_name} ({corp_code}), year={year}")
        print(f"  - rcept_no={rcept_no}")

        # 이미 allocation_tables 가 채워져 있으면 스킵할 수도 있음 (원하면 조건 추가)
        # if item.get("allocation_tables"):
        #     print("  → 이미 allocation_tables 존재, 스킵\n")
        #     updated.append(item)
        #     continue

        if not rcept_no:
            print("  → rcept_no 없음, 스킵\n")
            updated.append(item)
            continue

        xml_text = fetch_document_xml(rcept_no)
        time.sleep(1.0)  

        if xml_text is None:
            print(" → document.xml 가져오기 실패, allocation_tables 비워둠\n")
            item["allocation_tables"] = []
            updated.append(item)
            continue

        allocations = parse_third_party_allocation(xml_text)
        print(f" → 제3자배정 배정대상자 {len(allocations)}명 추출")

        item["allocation_tables"] = allocations
        updated.append(item)
        print()

    # 2) 결과 저장
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    print("\n완료!")
    print(f"   → 저장 파일: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_fill_allocation_tables()
