import json
import math

INPUT_EDGE_FILE = "./output/hyslrSttus_edges.json"
CHANGE_OUTPUT_FILE = "./output/hyslrSttus_changes.json"
SNAPSHOT_OUTPUT_FILE = "./output/hyslrSttus_snapshot.json"

def is_zero(val, eps=1e-9):
    if val is None:
        return True
    try:
        return abs(float(val)) < eps
    except Exception:
        return True

def main():
    with open(INPUT_EDGE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    edges = data.get("edges", [])

    change_events = []
    snapshots = []

    for e in edges:
        props = e.get("properties", {})
        edge_type = e.get("type")
        company_id = e.get("target")
        company_name = e.get("target_name")
        shareholder_id = e.get("source")
        shareholder_name = e.get("source_name")

        ratio_begin = props.get("ratio_begin")
        ratio_end = props.get("ratio_end")
        ratio_delta = props.get("ratio_delta")
        shares_begin = props.get("shares_begin")
        shares_end = props.get("shares_end")
        shares_delta = props.get("shares_delta")

        bsns_year = props.get("bsns_year")
        as_of = props.get("as_of")
        relation = props.get("relation_se")
        rcept_no = props.get("rcept_no")
        rm = props.get("rm")
        stock_kind = props.get("stock_kind")

        # 1) 지분 변동 있는 케이스만 CHANGE 이벤트로 수집
        if not is_zero(ratio_delta):
            change_events.append(
                {
                    "edge_type": edge_type,
                    "company_id": company_id,
                    "company_name": company_name,
                    "shareholder_id": shareholder_id,
                    "shareholder_name": shareholder_name,
                    "bsns_year": bsns_year,
                    "as_of": as_of,
                    "relation": relation,
                    "stock_kind": stock_kind,
                    "before_ratio": ratio_begin,
                    "after_ratio": ratio_end,
                    "delta_ratio": ratio_delta,
                    "before_shares": shares_begin,
                    "after_shares": shares_end,
                    "delta_shares": shares_delta,
                    "reason": rm,
                    "rcept_no": rcept_no,
                }
            )
        else:
            # 2) 나머지는 그냥 "상태" 정보만 간단히
            snapshots.append(
                {
                    "edge_type": edge_type,
                    "company_id": company_id,
                    "company_name": company_name,
                    "shareholder_id": shareholder_id,
                    "shareholder_name": shareholder_name,
                    "bsns_year": bsns_year,
                    "as_of": as_of,
                    "relation": relation,
                    "stock_kind": stock_kind,
                    "ratio": ratio_end,
                    "shares": shares_end,
                }
            )

    with open(CHANGE_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"changes": change_events}, f, ensure_ascii=False, indent=2)

    with open(SNAPSHOT_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"snapshots": snapshots}, f, ensure_ascii=False, indent=2)

    print("분리 완료")
    print(f" - 지분 변동 이벤트 개수: {len(change_events)} → {CHANGE_OUTPUT_FILE}")
    print(f" - 단순 스냅샷 개수: {len(snapshots)} → {SNAPSHOT_OUTPUT_FILE}")

if __name__ == "__main__":
    main()
