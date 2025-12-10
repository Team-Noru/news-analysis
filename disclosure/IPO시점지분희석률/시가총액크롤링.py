import requests
from bs4 import BeautifulSoup
import json
import time

BASE_URL = "https://finance.naver.com/sise/sise_market_sum.naver"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

def parse_market_page(sosok: int, page: int):
    params = {
        "sosok": str(sosok),  # 0: 코스피, 1: 코스닥
        "page": str(page),
    }
    res = requests.get(BASE_URL, params=params, headers=HEADERS)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    table = soup.select_one("table.type_2")
    if not table:
        return []

    rows = table.select("tbody > tr")
    results = []

    for tr in rows:
        tds = tr.find_all("td")

        if len(tds) < 10:
            continue

        name_cell = tds[1]
        a_tag = name_cell.find("a")
        if not a_tag:
            continue

        name = a_tag.get_text(strip=True)
        href = a_tag["href"] 
        code = href.split("code=")[-1]

        mcap_text = tds[6].get_text(strip=True).replace(",", "")
        if mcap_text == "":
            continue

        try:
            market_cap = int(mcap_text)
        except ValueError:
            continue

        results.append(
            {
                "name": name,
                "code": code,
                "market_cap_unit_million_krw": market_cap,
            }
        )

    return results

# 데이터 크롤링 (코스피, 코스닥 전체 종목 수집)
def crawl_market(sosok: int, market_name: str, max_pages: int = 50):

    all_items = []
    for page in range(1, max_pages + 1):
        page_items = parse_market_page(sosok, page)

        if not page_items:
            break

        for item in page_items:
            item["market"] = market_name

        all_items.extend(page_items)

        # 너무 빠른 요청 방지
        time.sleep(0.2)

    return all_items


def main():
    kospi_items = crawl_market(0, "KOSPI")
    kosdaq_items = crawl_market(1, "KOSDAQ")

    all_items = kospi_items + kosdaq_items

    print(f"KOSPI 종목 수: {len(kospi_items)}")
    print(f"KOSDAQ 종목 수: {len(kosdaq_items)}")
    print(f"총 종목 수: {len(all_items)}")

    # 결과 JSON으로 저장
    with open("naver_market_caps.json", "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)



if __name__ == "__main__":
    main()
