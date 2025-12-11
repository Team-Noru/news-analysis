import json
import os

CORP_FILE = "corp_merged.json"          # corp 리스트 파일
MCAP_FILE = "naver_market_caps.json"    # 시총 크롤링한 파일
OUTPUT_FILE = "company_list_market.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_name(name: str) -> str:
    if not name:
        return ""
    return (
        name.replace(" ", "")   
            .replace("㈜", "")
            .replace("(주)", "")
            .replace("주식회사", "")
            .strip()
    )


def main():
    if not os.path.exists(CORP_FILE):
        raise FileNotFoundError(CORP_FILE)
    if not os.path.exists(MCAP_FILE):
        raise FileNotFoundError(MCAP_FILE)

    corp_list = load_json(CORP_FILE)
    mcap_list = load_json(MCAP_FILE)

    # 시총 JSON -> 이름 기준 dict로 변환
    mcap_by_name = {}
    for item in mcap_list:
        raw_name = item.get("name")
        norm = normalize_name(raw_name)
        if not norm:
            continue

        # 같은 이름이 여러 번 나오면, 시총이 더 큰 쪽을 남김김
        if norm in mcap_by_name:
            if item.get("market_cap_unit_million_krw", 0) > mcap_by_name[norm].get(
                "market_cap_unit_million_krw", 0
            ):
                mcap_by_name[norm] = item
        else:
            mcap_by_name[norm] = item

    merged = []
    missed = []

    # corp_merged 한 줄씩 돌면서 이름 매칭
    for corp in corp_list:
        raw_name = corp.get("name")
        norm = normalize_name(raw_name)

        mcap_info = mcap_by_name.get(norm)
        if not mcap_info:
            missed.append(raw_name)
            continue

        
        merged_item = {
            **corp,
            "krx_code": mcap_info.get("code"),
            "market": mcap_info.get("market"),
            "market_cap_unit_million_krw": mcap_info.get("market_cap_unit_million_krw"),
        }
        merged.append(merged_item)

    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"merge 완료: {len(merged)}개 → {OUTPUT_FILE}")
    print(f"corp_merged 에만 있고 시총 JSON에는 없는 회사 수: {len(missed)}")



if __name__ == "__main__":
    main()
