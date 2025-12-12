import io
import zipfile
import requests
from dotenv import load_dotenv
import os

load_dotenv()
DART_KEY = os.getenv("OPEN_DART_API_KEY")

DOC_URL = "https://opendart.fss.or.kr/api/document.xml"

# document.xml API 호출 후 원본 파일 받아오기
def fetch_document_xml(rcept_no: str) -> str | None:
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
                return None

            xml_name = xml_candidates[0]
            xml_bytes = z.read(xml_name)

        try:
            xml_text = xml_bytes.decode("euc-kr")
        except UnicodeDecodeError:
            xml_text = xml_bytes.decode("utf-8", errors="ignore")

        return xml_text

    except zipfile.BadZipFile:

    try:
        txt = raw.decode("euc-kr")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", errors="ignore")

    if "오류가 발생하였습니다" in txt or "접수번호 오류" in txt:
        return None

    return txt

# xml 파일을 ./debug_docs 밑에 저장하는 함수
def save_debug_xml(rcept_no: str, xml_text: str, corp_name: str | None = None):
    os.makedirs("./debug_docs", exist_ok=True)

    safe_name = corp_name or "unknown"
    safe_name = "".join(c for c in safe_name if c.isalnum())

    filename = f"document_{safe_name}_{rcept_no}.xml"
    path = os.path.join("./debug_docs", filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)




if __name__ == "__main__":
    # 테스트
    rcept_no = "20240802000202"  # 예시 문서 number

    xml_text = fetch_document_xml(rcept_no)

    if xml_text is None:
        print("document.xml 가져오기 실패")
    else:
        print("document.xml 가져오기 성공, 앞 40줄만 출력\n")
        lines = xml_text.splitlines()
        for i, line in enumerate(lines[:40], start=1):
            print(f"{i:03}: {line}")

        save_debug_xml(rcept_no, xml_text, corp_name="인투셀")
