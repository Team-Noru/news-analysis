import json

INPUT_EDGE_FILE = "./output/otr_invest_edges.json"
OUTPUT_EDGE_FILE = "./output/otr_invest_edges_top30.json"

# 코스피 시총 Top 30 기업 이름 목록
TOP30_NAMES = {
    "삼성전자",
    "SK하이닉스",
    "LG에너지솔루션",
    "삼성바이오로직스",
    "한화에어로스페이스",
    "KB금융",
    "현대차",
    "HD현대중공업",
    "기아",
    "셀트리온",
    "두산에너빌리티",
    "NAVER",
    "한화오션",
    "신한지주",
    "삼성물산",
    "삼성생명",
    "카카오",
    "HD한국조선해양",
    "SK스퀘어",
    "현대모비스",
    "하나금융지주",
    "현대로템",
    "HMM",
    "POSCO홀딩스",
    "한국전력",
    "HD현대일렉트릭",
    "삼성화재",
    "메리츠금융지주",
    "LG화학",
    "우리금융지주",
}

def main():
    with open(INPUT_EDGE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    edges = data.get("edges", [])
    
    filtered_edges = [
        e for e in edges 
        if e.get("source_name") in TOP30_NAMES
    ]

    with open(OUTPUT_EDGE_FILE, "w", encoding="utf-8") as f:
        json.dump({"edges": filtered_edges}, f, ensure_ascii=False, indent=2)

    print("완료!")
    print(f"- 전체 edge 개수: {len(edges)}")
    print(f"- Top30 출발 edge 개수: {len(filtered_edges)}")
    print(f"- 저장 위치: {OUTPUT_EDGE_FILE}")

if __name__ == "__main__":
    main()
