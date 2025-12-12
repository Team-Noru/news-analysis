"""
- 목적:
  제3자배정 이벤트 목록(JSON)을 기반으로 document.xml을 재조회하고,
  배정대상자(THD_ASN_LST) 테이블을 파싱하여 allocation_tables를 채운다.
  중간에 끊겨도 복구 가능하도록 partial 파일을 매번 저장한다.

- 입력:
  - ./output/capital_increase_third_party_tables.json

- 처리:
  1) rcept_no로 document.xml(zip/xml) 다운로드
  2) THD_ASN_LST 파싱
  3) 합계/소계 행 등 노이즈 행 제거
  4) 매 이벤트마다 partial 파일 저장 (checkpoint)

- 출력:
  - ./output/capital_increase_third_party_table_with_alloc.partial.json (checkpoint)
  - ./output/capital_increase_third_party_table_with_alloc.json (final)
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
PARTIAL_FILE = "./output/capital_increase_third_party_table_with_alloc.partial.json"


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
# 2) XML에서 제3자배정 '배정대상자 테이블' 파싱 (+ 합계행 필터링)
# ---------------------------
def parse_third_party_allocation(xml_text: str) -> List[Dict[str, Any]]:
    """
    document.xml 안에서 ACLASS="THD_ASN_LST" 인 TABLE-GROUP을 찾아
    제3자배정 '배정대상자' 테이블 파싱

    반환 값 예시:
    [
      {
        "name": "광혁건설",
        "relation": "관계없음",
        "reason": "...",
        "trade_history": "...",
        "assigned_shares": "176,470",
        "remark": "-"
      },
      ...
    ]
    """
    soup = BeautifulSoup(xml_text, "lxml-xml")

    tg = soup.find("TABLE-GROUP", {"ACLASS": "THD_ASN_LST"})
    if tg is None:
        return []

    raw_rows: List[Dict[str, Any]] = []

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

        # 최소한 name 이 있는 행만 유효한 데이터로 본다 (헤더/빈 행 제거)
        if "name" in row:
            # 공백 정리
            row["name"] = (row.get("name") or "").strip()
            row["relation"] = (row.get("relation") or "").strip() or None
            row["reason"] = (row.get("reason") or "").strip() or None
            row["trade_history"] = (row.get("trade_history") or "").strip() or None
            row["assigned_shares"] = (row.get("assigned_shares") or "").strip() or None
            row["remark"] = (row.get("remark") or "").strip() or None

            raw_rows.append(row)

    # 합계 행(계/합계/소계 등) 필터링
    cleaned: List[Dict[str, Any]] = []
    for row in raw_rows:
        name = (row.get("name") or "").strip()
        relation = (row.get("relation") or "").strip() if row.get("relation") else ""
        reason = (row.get("reason") or "").strip() if row.get("reason") else ""
        trade_history = (row.get("trade_history") or "").strip() if row.get("trade_history") else ""

        # 합계/소계/계 등으로 보이는 행 여부
        is_total_like = (
            name in ("계", "합계", "소계")
            or name.endswith(" 계")
            or name.endswith(" 합계")
            or name.endswith(" 소계")
        )

        # 내용이 거의 없는 경우(모두 '-' 이거나 빈값)
        mostly_empty = all(
            v in ("", "-", None)
            for v in [relation, reason, trade_history]
        )

        if is_total_like and mostly_empty:
            # 합계 행이므로 스킵
            continue

        cleaned.append(row)

    return cleaned


# ---------------------------
# 3) 전체 JSON을 돌면서 allocation_tables 채우기
# ---------------------------
def run_fill_allocation_tables():
    # 1) 입력 JSON 로드
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    print(f"입력 이벤트 개수: {total}\n")

    updated: List[Dict[str, Any]] = []

    # 혹시 PARTIAL_FILE 이 이미 있으면, 재시도 시 이어서 쓸 수도 있음
    # (지금은 간단하게 무시하고 새로 도는 형태로 둠)
    # 필요하면 여기서 로드 로직 추가해도 됨.

    for idx, item in enumerate(data, start=1):
        corp_code = item.get("corp_code")
        corp_name = item.get("corp_name")
        year = item.get("year")
        event = item.get("event") or {}
        rcept_no = event.get("rcept_no")

        print("=" * 60)
        print(f"({idx}/{total}) {corp_name} ({corp_code}), year={year}")
        print(f"  - rcept_no={rcept_no}")

        if not rcept_no:
            print("  → rcept_no 없음, allocation_tables 비움\n")
            item["allocation_tables"] = []
            updated.append(item)
        else:
            xml_text = fetch_document_xml(rcept_no)
            time.sleep(1.0)  # API 부하 방지 

            if xml_text is None:
                print("  → document.xml 가져오기 실패, allocation_tables 비워둠\n")
                item["allocation_tables"] = []
                updated.append(item)
            else:
                try:
                    allocations = parse_third_party_allocation(xml_text)
                    print(f"  → 제3자배정 배정대상자 {len(allocations)}명 추출 (합계 행 제거 후)")
                except Exception as e:
                    print(f"[WARN] XML 파싱 중 오류 발생: rcept_no={rcept_no}, 이유={e}")
                    allocations = []

                item["allocation_tables"] = allocations
                updated.append(item)
                print()

        # 매 건마다 PARTIAL_FILE로 중간 저장해서, 중간에 끊겨도 여기까지 남도록
        try:
            with open(PARTIAL_FILE, "w", encoding="utf-8") as pf:
                json.dump(updated, pf, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] PARTIAL_FILE 저장 실패: {e}")

    # 2) 전체 완료 후 최종 파일로 저장
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    print("\n전체 처리 완료!")
    print(f"   → 중간 결과(백업): {PARTIAL_FILE}")
    print(f"   → 최종 결과: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_fill_allocation_tables()
