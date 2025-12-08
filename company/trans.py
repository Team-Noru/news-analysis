import pandas as pd
import json
from pathlib import Path
EXCEL_PATH = Path("상장법인목록.xls") 
OUTPUT_JSON = Path("listed_companies_korea.json")

MARKET_MAP = {
    "유가": "KOSPI",
    "코스피": "KOSPI",
    "코스닥": "KOSDAQ",
    "코넥스": "KONEX",
    "KOSPI": "KOSPI",
    "KOSDAQ": "KOSDAQ",
    "KONEX": "KONEX",
}

def normalize_market(market_raw: str):
    if not isinstance(market_raw, str):
        return None
    return MARKET_MAP.get(market_raw.strip(), None)


def load_companies_from_excel(path: Path):
    try:
        df = pd.read_excel(path)
    except Exception as e:
        df_list = pd.read_html(path, header=0)
        df = df_list[0]

    col_name = {
        "회사명": "name",
        "시장구분": "market_raw",
        "종목코드": "ticker",
        "업종": "industry",
        "주요제품": "main_products",
        "상장일": "list_date",
        "결산월": "fiscal_month",
        "대표자명": "ceo",
        "홈페이지": "homepage",
        "지역": "region",
    }

    df = df[list(col_name.keys())].rename(columns=col_name)

    # 스팩 행 제거 (회사명에 '스팩'이 들어간 경우 전부 삭제)
    df = df[~df["name"].astype(str).str.contains("스팩", case=False)]
    
    df["ticker"] = df["ticker"].astype(str)
    df["exchange"] = df["market_raw"].apply(normalize_market)

    return df.to_dict(orient="records")

def main():
    companies = load_companies_from_excel(EXCEL_PATH)

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(companies, f, ensure_ascii=False, indent=2)

    print(f"총 {len(companies)}개 종목을 {OUTPUT_JSON} 에 저장 완료!")


if __name__ == "__main__":
    main()
