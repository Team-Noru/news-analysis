import os
import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPEN_DART_API_KEY")
if not API_KEY:
    raise RuntimeError("OPEN_DART_API_KEY 가 .env 에 없습니다!")

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"

OUT_CSV = Path("dart_corp_code.csv")
OUT_JSON = Path("dart_corp_code.json")


def download_and_parse_corp_code():
    """
    corpCode.xml(zip) 전체 받아서
    corp_code / corp_name / corp_eng_name / stock_code / modify_date
    테이블로 변환
    """
    print("[INFO] corpCode.xml zip 다운로드 중...")
    import requests

    params = {"crtfc_key": API_KEY}
    resp = requests.get(CORP_CODE_URL, params=params, timeout=30)
    resp.raise_for_status()

    # 응답은 zip 바이너리
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    # 보통 내부에 xml 파일 1개만 있음
    inner_name = zf.namelist()[0]
    xml_bytes = zf.read(inner_name)

    print("[INFO] XML 파싱 중...")
    root = ET.fromstring(xml_bytes)

    rows = []
    for el in root.findall("list"):
        rows.append(
            {
                "corp_code": el.findtext("corp_code"),          # 8자리 고유번호
                "corp_name": el.findtext("corp_name"),          # 한글 정식명칭
                "corp_eng_name": el.findtext("corp_eng_name"),  # 영문 정식명칭
                "stock_code": el.findtext("stock_code"),        # 6자리 종목코드(상장사만)
                "modify_date": el.findtext("modify_date"),      # YYYYMMDD
            }
        )

    df = pd.DataFrame(rows)
    print(f"[INFO] 총 {len(df)}개 기업 로드 완료")

    # CSV 저장
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[INFO] CSV 저장 완료 → {OUT_CSV}")

    # JSON 저장
    df.to_json(OUT_JSON, orient="records", force_ascii=False, indent=2)
    print(f"[INFO] JSON 저장 완료 → {OUT_JSON}")

    return df


if __name__ == "__main__":
    df = download_and_parse_corp_code()
    # 상장사만 보고 싶으면:
    listed = df[df["stock_code"].notna() & (df["stock_code"] != "")]
    print("[INFO] 상장사 개수:", len(listed))
    print(listed.head())
