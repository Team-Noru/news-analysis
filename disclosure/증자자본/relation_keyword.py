# .output/capital_increase_third_party_full.json에서 의미있는 관계가 있나 확인하기 위해 relation 유니크한 키워드만 추출하고자 한다
import json

INPUT_PATH = "./output/capital_increase_third_party_full.json"

def extract_unique_relations(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    relations = set()

    for item in data:
        allocs = item.get("allocation_tables", [])
        for row in allocs:
            rel = row.get("relation")
            if rel:
                relations.add(rel.strip())

    return sorted(relations)


if __name__ == "__main__":
    unique_relations = extract_unique_relations(INPUT_PATH)

    print("총 relation 종류:", len(unique_relations))
    print("=====================================")
    for r in unique_relations:
        print(r)
