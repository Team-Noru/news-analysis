import os
import json
import csv
import math
import unicodedata
from typing import Dict, Any, List, Optional

# -----------------------------
#  설정: 입력 / 출력 경로
# -----------------------------
BASE_DIR = "./output"

CAPITAL_INCREASE_PATH = os.path.join(BASE_DIR, "capital_increase_edges_clean.json")
OWNERSHIP_CHANGE_PATH = os.path.join(BASE_DIR, "ownership_change_alerts_mcap.json")
IPO_DILUTION_PATH = os.path.join(BASE_DIR, "ipo_dilution_events_mcap.json")

NODES_CSV_PATH = os.path.join(BASE_DIR, "graph_nodes.csv")
EDGES_CSV_PATH = os.path.join(BASE_DIR, "graph_edges.csv")


# -----------------------------
#  문자열 정규화 유틸
# -----------------------------
def normalize_name_key(name: str) -> str:
    """
    이름을 키로 쓰기 위한 정규화:
    - NFKC 정규화
    - 소문자
    - 공백 제거
    - (),[],주식회사,㈜,쉼표 등 제거
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", str(name))
    s = s.lower()
    # 자주 나오는 노이즈 제거
    for token in ["주식회사", "㈜", "(주)", " ", ",", ".", "(", ")", "[", "]"]:
        s = s.replace(token, "")
    return s.strip()


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "" or (isinstance(x, str) and x.strip() == "-"):
            return None
        return float(str(x).replace(",", ""))
    except Exception:
        return None


# -----------------------------
#  엔티티 타입 분류
# -----------------------------
def classify_entity_type_from_name(name: str) -> str:
    """
    이름만 보고 대략적인 타입 분류:
    - 금융기관(FIN_INST)
    - 펀드/VC(FUND_VC)
    - 그 외(PERSON_OR_ETC)
    """
    if not name:
        return "UNKNOWN"

    s = name

    # 금융기관 키워드
    fin_keywords = ["은행", "증권", "자산운용", "자산 운용", "투자증권", "캐피탈", "보험", "금융", "신탁"]
    if any(k in s for k in fin_keywords):
        return "FIN_INST"

    # 펀드/VC 키워드
    fund_keywords = ["투자조합", "신기술", "벤처", "venture", "fund", "펀드", "private equity", "pe"]
    if any(k in s.lower() for k in fund_keywords) or "조합" in s:
        return "FUND_VC"

    # 그 외
    return "PERSON_OR_ETC"


# -----------------------------
#  Node Registry
# -----------------------------
class NodeRegistry:
    def __init__(self):
        # corp_code 기준 회사 노드
        self.corp_nodes: Dict[str, Dict[str, Any]] = {}
        # 이름 기준 엔티티 노드 (회사 아닌 투자자/주주 등)
        self.entity_nodes: Dict[str, Dict[str, Any]] = {}
        # corp_name 정규화 → corp_code 매핑 (회사명으로 투자자 매칭용)
        self.corp_name_key_to_code: Dict[str, str] = {}
        # node_id 카운터 (엔티티용)
        self._entity_seq = 1

    # ---------- 회사 노드 등록 ----------
    def register_company(self, corp_code: str, corp_name: str,
                        market: Optional[str] = None,
                        cap_bucket: Optional[str] = None,
                        mcap_eok: Optional[float] = None):
        if not corp_code:
            return

        node_id = f"corp:{corp_code}"
        node = self.corp_nodes.get(corp_code)
        if node is None:
            node = {
                "node_id": node_id,
                "name": corp_name,
                "entity_type": "COMPANY",
                "corp_code": corp_code,
                "market": market or "",
                "cap_bucket": cap_bucket or "",
                "market_cap_unit_eok_krw": mcap_eok,
            }
            self.corp_nodes[corp_code] = node
        else:
            # 정보가 비어있으면 채워 넣기
            if market and not node.get("market"):
                node["market"] = market
            if cap_bucket and not node.get("cap_bucket"):
                node["cap_bucket"] = cap_bucket
            if mcap_eok is not None and node.get("market_cap_unit_eok_krw") is None:
                node["market_cap_unit_eok_krw"] = mcap_eok

        # 이름 → corp_code 매핑 (투자자 이름이 상장사 이름과 같으면 회사로 매핑)
        if corp_name:
            key = normalize_name_key(corp_name)
            if key and key not in self.corp_name_key_to_code:
                self.corp_name_key_to_code[key] = corp_code

    # ---------- 회사 노드 가져오기 ----------
    def get_company_node_id(self, corp_code: str) -> Optional[str]:
        if corp_code in self.corp_nodes:
            return self.corp_nodes[corp_code]["node_id"]
        return None

    # ---------- 투자자/주주 노드 가져오기/생성 ----------
    def get_or_create_entity(self, name: str) -> str:
        """
        투자자 / 주주 이름이 회사명과 같으면 회사 노드로 통합,
        아니면 별도 ENTITY 노드 생성
        """
        if not name:
            # 이름 없는 경우는 그냥 에러 방지용 dummy
            name = "UNKNOWN"

        key = normalize_name_key(name)

        # 1) 상장사 이름과 매칭되는 경우 → 회사 노드 재사용
        corp_code = self.corp_name_key_to_code.get(key)
        if corp_code is not None and corp_code in self.corp_nodes:
            return self.corp_nodes[corp_code]["node_id"]

        # 2) 이미 있는 엔티티면 재사용
        if key in self.entity_nodes:
            return self.entity_nodes[key]["node_id"]

        # 3) 새 엔티티 노드 생성
        node_id = f"ent:{self._entity_seq}"
        self._entity_seq += 1

        entity_type = classify_entity_type_from_name(name)

        node = {
            "node_id": node_id,
            "name": name,
            "entity_type": entity_type,
            "corp_code": "",
            "market": "",
            "cap_bucket": "",
            "market_cap_unit_eok_krw": None,
        }
        self.entity_nodes[key] = node
        return node_id

    # ---------- 모든 노드 리스트 반환 ----------
    def all_nodes(self) -> List[Dict[str, Any]]:
        return list(self.corp_nodes.values()) + list(self.entity_nodes.values())


#  1) 회사 엔티티 정규화
def build_corp_registry(node_reg: NodeRegistry,
                        cap_inc_items: List[Dict[str, Any]],
                        own_items: List[Dict[str, Any]],
                        ipo_items: List[Dict[str, Any]]):

    # 유상증자 데이터에서 회사 정보 모으기
    for e in cap_inc_items:
        node_reg.register_company(
            corp_code=e.get("corp_code"),
            corp_name=e.get("corp_name"),
            market=e.get("market"),
            cap_bucket=e.get("cap_bucket"),
            mcap_eok=safe_float(e.get("market_cap_unit_eok_krw")),
        )

    # 최대주주변동 데이터에서 회사 정보 모으기
    for item in own_items:
        node_reg.register_company(
            corp_code=item.get("corp_code"),
            corp_name=item.get("corp_name"),
            market=item.get("market"),
            cap_bucket=item.get("cap_bucket"),
            mcap_eok=safe_float(item.get("market_cap_unit_eok_krw")),
        )

    # IPO 희석 데이터에서 회사 정보 모으기
    for item in ipo_items:
        node_reg.register_company(
            corp_code=item.get("corp_code"),
            corp_name=item.get("corp_name"),
            market=item.get("market"),
            cap_bucket=item.get("cap_bucket"),
            mcap_eok=safe_float(item.get("market_cap_unit_eok_krw")),
        )


#  2) capital_increase_edges → Edges
def build_edges_from_capital_increase(ci_data, node_reg):
    edges = []

    for rec in ci_data:
        investor_name = rec.get("source_name")
        issuer_code = rec.get("target_corp_code")
        issuer_name = rec.get("target_corp_name")
        relation_type = rec.get("relation_type") or "CAPITAL_INCREASE_PARTICIPATION"
        meta = rec.get("meta") or {}

        if not investor_name or not issuer_code:
            continue

        issuer_node_id = node_reg.get_company_node_id(issuer_code)
        if not issuer_node_id:
            node_reg.register_company(
                corp_code=issuer_code,
                corp_name=issuer_name
            )
            issuer_node_id = node_reg.get_company_node_id(issuer_code)

        investor_node_id = node_reg.get_or_create_entity(investor_name)

        assigned_shares = meta.get("assigned_shares")
        relationship_strength = None
        if isinstance(assigned_shares, (int, float)):
            relationship_strength = float(assigned_shares)

        rcept_no = meta.get("rcept_no")
        event_date = (
            meta.get("payment_date")
            or meta.get("decide_date")
            or meta.get("issue_date")
        )

        edge = {
            "from_id": investor_node_id,          # 투자자 → 발행사
            "to_id": issuer_node_id,
            "rel_type": "CAPITAL_INCREASE",       # 상위 카테고리
            "event_type": "CAPITAL_INCREASE",
            "event_tag": relation_type,           # PARTICIPATION / LEAD 등
            "event_date": event_date,
            "rcept_no": rcept_no,
            "weight": relationship_strength,      # strength → weight
            "source_json": "capital_increase",
            "extra_json": json.dumps(meta, ensure_ascii=False),
        }

        edges.append(edge)

    print(f"[INFO] edges from capital increase: {len(edges)}")
    return edges


#  3 ) ownership_change_alerts → Edges
def build_edges_from_ownership_change(node_reg: NodeRegistry, items: List[Dict[str, Any]]):
    edges = []

    for item in items:
        corp_code = item.get("corp_code")
        corp_node_id = node_reg.get_company_node_id(corp_code)
        if not corp_node_id:
            continue

        holder_name = item.get("holder")
        if not holder_name:
            continue

        holder_node_id = node_reg.get_or_create_entity(holder_name)

        change_ratio_abs = safe_float(item.get("change_ratio_abs"))
        before_ratio = safe_float(item.get("before_ratio"))
        after_ratio = safe_float(item.get("after_ratio"))

        event_tag = item.get("alert_type") or ""
        if before_ratio is not None and after_ratio is not None:
            if before_ratio < 30 <= after_ratio:
                event_tag = (event_tag + "|CONTROL_GAIN").strip("|")
            elif after_ratio < 30 <= before_ratio:
                event_tag = (event_tag + "|CONTROL_LOSS").strip("|")

        edge = {
            "from_id": holder_node_id,
            "to_id": corp_node_id,
            "rel_type": "OWNERSHIP_CHANGE",
            "event_type": "OWNERSHIP_CHANGE",
            "weight": change_ratio_abs,
            "event_tag": event_tag,
            "event_date": item.get("change_on") or item.get("stlm_dt") or item.get("report_dt"),
            "rcept_no": item.get("rcept_no"),
            "source_json": "ownership_change",
            "extra_json": json.dumps({
                "before_ratio": before_ratio,
                "after_ratio": after_ratio,
                "trans_kind": item.get("trans_kind"),
                "alert_type": item.get("alert_type"),
            }, ensure_ascii=False),
        }
        edges.append(edge)

    return edges


#  4) ipo_dilution_events → Edges
def build_edges_from_ipo_dilution(node_reg: NodeRegistry,
                                items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    edges = []

    for item in items:
        corp_code = item.get("corp_code")
        corp_node_id = node_reg.get_company_node_id(corp_code)
        if not corp_node_id:
            continue

        holder_name = item.get("holder")
        if not holder_name:
            continue

        holder_node_id = node_reg.get_or_create_entity(holder_name)

        dilution_pp = safe_float(item.get("dilution_pp"))
        dilution_pct = safe_float(item.get("dilution_pct"))
        prev_ratio = safe_float(item.get("prev_ratio"))
        curr_ratio = safe_float(item.get("curr_ratio"))

        # event_tag 규칙
        tags = []
        if dilution_pp is not None and dilution_pp >= 10:
            tags.append("SIGNIFICANT_DILUTION")
        if prev_ratio is not None and curr_ratio is not None:
            if prev_ratio >= 30 and curr_ratio < 30:
                tags.append("CONTROL_LOSS_BY_IPO")
        event_tag = "|".join(tags) if tags else ""

        edge = {
            "from_id": holder_node_id,
            "to_id": corp_node_id,
            "rel_type": "IPO_DILUTION",
            "event_type": "IPO_DILUTION",
            "weight": dilution_pct,
            "event_tag": event_tag,
            "event_date": item.get("stlm_dt") or item.get("base_date"),
            "rcept_no": item.get("rcept_no"),
            "source_json": "ipo_dilution",
            "extra_json": json.dumps({
                "prev_ratio": prev_ratio,
                "curr_ratio": curr_ratio,
                "dilution_pp": dilution_pp,
                "dilution_pct": dilution_pct,
                "change_cause": item.get("change_cause"),
            }, ensure_ascii=False),
        }
        edges.append(edge)

    return edges


# CSV 저장
def save_nodes_to_csv(nodes: List[Dict[str, Any]], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    fieldnames = [
        "node_id",
        "name",
        "entity_type",
        "corp_code",
        "market",
        "cap_bucket",
        "market_cap_unit_eok_krw",
    ]

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for node in nodes:
            row = {k: node.get(k, "") for k in fieldnames}
            writer.writerow(row)


def save_edges_to_csv(edges: List[Dict[str, Any]], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    fieldnames = [
        "edge_id",
        "from_id",
        "to_id",
        "rel_type",
        "event_type",
        "event_tag",
        "event_date",
        "rcept_no",
        "weight",
        "source_json",
        "extra_json",
    ]

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, edge in enumerate(edges, start=1):
            row = {k: edge.get(k, "") for k in fieldnames if k != "edge_id"}
            row["edge_id"] = f"e{i}"
            writer.writerow(row)



def main():
    # input JSON 로드
    with open(CAPITAL_INCREASE_PATH, "r", encoding="utf-8") as f:
        cap_inc_items = json.load(f)

    with open(OWNERSHIP_CHANGE_PATH, "r", encoding="utf-8") as f:
        own_json = json.load(f)
        own_items = own_json.get("items", [])

    with open(IPO_DILUTION_PATH, "r", encoding="utf-8") as f:
        ipo_json = json.load(f)
        ipo_items = ipo_json.get("items", [])

    print(f"[INFO] capital_increase_edges_clean: {len(cap_inc_items)} rows")
    print(f"[INFO] ownership_change_alerts_mcap: {len(own_items)} rows")
    print(f"[INFO] ipo_dilution_events_mcap: {len(ipo_items)} rows")

    # 엔티티 정규화: 회사들 먼저 Registry에 등록
    node_reg = NodeRegistry()
    build_corp_registry(node_reg, cap_inc_items, own_items, ipo_items)
    print(f"[INFO] registered companies: {len(node_reg.corp_nodes)}")

    # 각 JSON → edge 리스트
    edges_ci = build_edges_from_capital_increase(cap_inc_items, node_reg)
    edges_oc = build_edges_from_ownership_change(node_reg, own_items)
    edges_ipo = build_edges_from_ipo_dilution(node_reg, ipo_items)

    all_edges = edges_ci + edges_oc + edges_ipo
    print(f"[INFO] edges from capital increase: {len(edges_ci)}")
    print(f"[INFO] edges from ownership change: {len(edges_oc)}")
    print(f"[INFO] edges from ipo dilution: {len(edges_ipo)}")
    print(f"[INFO] total edges: {len(all_edges)}")

    # 노드/엣지 CSV 저장
    all_nodes = node_reg.all_nodes()
    print(f"[INFO] total nodes: {len(all_nodes)}")

    save_nodes_to_csv(all_nodes, NODES_CSV_PATH)
    save_edges_to_csv(all_edges, EDGES_CSV_PATH)

    print()
    print(f"nodes.csv  → {NODES_CSV_PATH}")
    print(f"edges.csv  → {EDGES_CSV_PATH}")


if __name__ == "__main__":
    main()
