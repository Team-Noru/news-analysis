# -----------------------------
# 공통 유틸
# -----------------------------
from datetime import datetime

def to_float_ratio(val):
    """
    '81.84%', '81.84 %', '81.84' → float 로 변환. 실패 시 None.
    괄호 음수 표현 (예: '(1.23)') 도 지원.
    """
    if val in ["", "-", None, " "]:
        return None
    s = str(val)
    s = s.replace("%", "").replace("％", "").strip()
    s = s.replace(",", "")

    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    try:
        num = float(s)
    except ValueError:
        return None

    return -num if is_negative else num


def to_int(val):
    """
    '1,234', '(1,234)' 같은 문자열을 int 로 변환. 실패 시 None.
    """
    if val in ["", "-", None, " "]:
        return None
    s = str(val).strip()
    s = s.replace(",", "")

    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    if not s.isdigit():
        return None

    num = int(s)
    return -num if is_negative else num


def parse_date_str(date_str: str):
    """
    change_on 예: '2022년 01월 22일' → '2022-01-22'
    - 공백 제거 후 '%Y년%m월%d일' 형식으로 파싱 시도
    - 실패하면 원본 문자열 그대로 반환
    """
    if not date_str:
        return None
    s = date_str.replace(" ", "").strip()
    try:
        # '2022년01월22일'
        dt = datetime.strptime(s, "%Y년%m월%d일")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        # 이미 'YYYY-MM-DD' 형태이거나 파싱 불가한 경우
        return date_str