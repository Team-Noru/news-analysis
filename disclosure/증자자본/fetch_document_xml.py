import io
import os
import zipfile
import requests
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

DOC_URL = "https://opendart.fss.or.kr/api/document.xml"


def fetch_document_xml(rcept_no: str) -> Optional[str]:
    """
    DART document.xml API 호출 유틸리티

    처리 흐름:
    1) API 호출
    2) ZIP 응답이면 → XML 파일 추출
    3) ZIP 아니면 → 텍스트(XML)로 디코딩 시도
    4) 오류 응답이면 None 반환
    """

    params = {
        "crtfc_key": DART_KEY,
        "rcept_no": rcept_no,
    }

    try:
        resp = requests.get(DOC_URL, params=params, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"document.xml 요청 실패: rcept_no={rcept_no}, 이유={e}")
        return None

    raw = resp.content


    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml_files = [n for n in z.namelist() if n.lower().endswith(".xml")]
            if not xml_files:
                return None

            xml_bytes = z.read(xml_files[0])

        try:
            return xml_bytes.decode("euc-kr")
        except UnicodeDecodeError:
            return xml_bytes.decode("utf-8", errors="ignore")

    except zipfile.BadZipFile:
        
        pass


    try:
        text = raw.decode("euc-kr")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="ignore")

    if "오류가 발생하였습니다" in text or "접수번호 오류" in text:
        return None

    return text


def save_debug_xml(
    rcept_no: str,
    xml_text: str,
    corp_name: Optional[str] = None
) -> None:
    """
    document.xml 원본을 debug_docs/ 아래에 저장 (디버깅 용도)
    """
    os.makedirs("./debug_docs", exist_ok=True)

    safe_name = corp_name or "unknown"
    safe_name = "".join(c for c in safe_name if c.isalnum())

    filename = f"document_{safe_name}_{rcept_no}.xml"
    path = os.path.join("./debug_docs", filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)


if __name__ == "__main__":
    # 테스트
    test_rcept_no = "20240802000202"

    xml_text = fetch_document_xml(test_rcept_no)

    if xml_text is None:
        print("document.xml 가져오기 실패")
    else:
        # print("document.xml 가져오기 성공 (앞 40줄)\n")
        # for i, line in enumerate(xml_text.splitlines()[:40], start=1):
        #     print(f"{i:03}: {line}")

        save_debug_xml(test_rcept_no, xml_text, corp_name="인투셀")
