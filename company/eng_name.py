import os
import requests
from typing import Optional, Dict
from dotenv import load_dotenv
# .env 파일 로드
load_dotenv()

BASE_URL = "https://engopendart.fss.or.kr/engapi/company.json"


def get_company_info(corp_code: str):
    """
    OpenDART 영문 API – 회사 기본정보 조회
    corp_code: 8자리 DART 법인코드
    """
    api_key = os.getenv("OPEN_DART_API_KEY")

    if not api_key:
        raise ValueError("ERROR: OPEN_DART_API_KEY 가 .env에서 로드되지 않았습니다.")

    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[HTTP ERROR] 요청 오류: {e}")
        return None

    data = resp.json()

    # status 체크
    status = data.get("status")
    message = data.get("message")

    if status != "000":
        print(f"[API ERROR] status={status}, message={message}")
        return None

    return data


if __name__ == "__main__":
    # 테스트용 법인코드 (8자리)
    test_code = "00126380"  # 원하는 코드로 변경

    result = get_company_info(test_code)

    if result:
        print("\n=== Company Info ===")
        print("법인명            :", result.get("corp_name"))
        print("영문명            :", result.get("corp_name_eng"))
        print("종목명            :", result.get("stock_name"))
        print("종목코드          :", result.get("stock_code"))
        print("소속시장(K/KOS/Y) :", result.get("corp_cls"))
        print("주소              :", result.get("adres"))
        print("홈페이지          :", result.get("hm_url"))
        print("IR URL           :", result.get("ir_url"))
        print("설립일            :", result.get("est_dt"))
        print("====================\n")