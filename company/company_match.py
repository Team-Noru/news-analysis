import json
import re
from pathlib import Path
from typing import List, Dict, Any


KOREA_JSON_PATH = Path("corp_merged.json")
US_JSON_PATH = Path("sp_500_list.json")


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_english_name(name: str) -> str:
    """
    영문 회사명에서 Co., Ltd., Inc., Corporation 같은 꼬리 조금 정리하기
    너무 aggressive 하게 자르지 말고, 흔한 suffix 정도만 제거
    """
    if not name:
        return ""
    n = name.strip()

    # 쉼표 기준으로 뒤 꼬리 날리기 (예: "Aimed Bio Inc." → "Aimed Bio Inc.")
    # 일단은 그대로 두고, suffix만 제거
    n = re.sub(
        r"\b(Co\.|Corporation|Corp\.|Inc\.|Incorporated|Ltd\.|Limited|Company)\b",
        "",
        n,
        flags=re.IGNORECASE,
    )
    # 여분의 공백/쉼표 정리
    n = re.sub(r"\s+", " ", n)
    n = n.strip(" ,")
    return n

def korean_word_boundary_match(text: str, word: str) -> bool:
    """
    한글 기업명이 부분 문자열로 잘못 매칭되는 것을 방지.
    앞뒤가 한글/영문/숫자가 아닌 경우만 매칭으로 인정.
    """
    pattern = rf"(?<![가-힣A-Za-z0-9]){re.escape(word)}(?![가-힣A-Za-z0-9])"
    return re.search(pattern, text) is not None


def build_company_index() -> List[Dict[str, Any]]:
    """
    한국 + 미국 기업 정보를 읽어서,
    각 기업별 alias 목록을 포함한 통합 인덱스를 만든다.
    """
    kor_list = load_json(KOREA_JSON_PATH)
    us_list = load_json(US_JSON_PATH)

    index: List[Dict[str, Any]] = []

    # 🇰🇷 한국 상장사
    for row in kor_list:
        aliases = set()

        name = (row.get("name") or "").strip()
        eng = (row.get("corp_eng_name") or "").strip()
        ticker = (row.get("ticker") or "").strip()

        if name:
            aliases.add(name)

        if eng:
            aliases.add(eng)
            simplified_eng = normalize_english_name(eng)
            if simplified_eng and simplified_eng.lower() != eng.lower():
                aliases.add(simplified_eng)

        # 필요하면 숫자 티커도 alias로:
        numeric_ticker = "".join(ch for ch in ticker if ch.isdigit())
        if numeric_ticker:
            aliases.add(numeric_ticker)

        if not aliases:
            continue

        index.append(
            {
                "source": "KR",
                "name": name,
                "corp_eng_name": eng,
                "ticker": ticker,
                "exchange": row.get("exchange"),
                "corp_code": row.get("corp_code"),
                "raw": row,  # 원본 전체 레코드
                "aliases": sorted(aliases, key=len, reverse=True),  # 길이 긴 것부터
            }
        )

    # 🇺🇸 미국 S&P 500
    for row in us_list:
        aliases = set()

        company = (row.get("company") or "").strip()
        company_kor = (row.get("company_kor") or "").strip()
        symbol = (row.get("symbol") or "").strip()

        if company:
            aliases.add(company)
            aliases.add(normalize_english_name(company))
        if company_kor:
            aliases.add(company_kor)
        if symbol:
            aliases.add(symbol)

        aliases = {a for a in aliases if a}  # 빈 문자열 제거

        if not aliases:
            continue

        index.append(
            {
                "source": "US",
                "company": company,
                "company_kor": company_kor,
                "symbol": symbol,
                "CIK": row.get("CIK"),
                "raw": row,
                "aliases": sorted(aliases, key=len, reverse=True),
            }
        )

    return index


def extract_companies_from_news(text: str, company_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    뉴스 본문(text)에서 어떤 기업이 언급됐는지 alias 기반으로 찾아낸다.
    - company_index: build_company_index() 결과
    """
    results = []

    # 소문자화 (한글엔 영향 없음)
    text_norm = text.lower()

    for comp in company_index:
        matched_aliases = []

        for alias in comp["aliases"]:
            alias_norm = alias.lower()
            if not alias_norm:
                continue

            # 알파벳(영문자)이 하나라도 들어간 alias → 단어 경계로 매칭
            if re.search(r"[a-z]", alias_norm):
                # \bNVDA\b, \bNvidia\b 이런 식
                pattern = r"\b" + re.escape(alias_norm) + r"\b"
                if re.search(pattern, text_norm):
                    matched_aliases.append(alias)
            else:
                if korean_word_boundary_match(text_norm, alias_norm):
                    matched_aliases.append(alias)

        if matched_aliases:
            # 중복 제거
            unique_matched = sorted(set(matched_aliases), key=len, reverse=True)
            result = {
                "source": comp["source"],
                "matched_aliases": unique_matched,
            }
            # 한국/미국 구분해서 필드 넣기
            if comp["source"] == "KR":
                result.update(
                    {
                        "name": comp.get("name"),
                        "corp_eng_name": comp.get("corp_eng_name"),
                        "ticker": comp.get("ticker"),
                        "exchange": comp.get("exchange"),
                        "corp_code": comp.get("corp_code"),
                    }
                )
            else:  # US
                result.update(
                    {
                        "company": comp.get("company"),
                        "company_kor": comp.get("company_kor"),
                        "symbol": comp.get("symbol"),
                        "CIK": comp.get("CIK"),
                    }
                )

            results.append(result)

    return results


if __name__ == "__main__":
    

    with open("news1.txt", "r", encoding="utf-8") as file:
        news_text = file.read()

    company_index = build_company_index()
    found = extract_companies_from_news(news_text, company_index)

    print("=== FOUND COMPANIES ===")
    for c in found:
        print(c)
