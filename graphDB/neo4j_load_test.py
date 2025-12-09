import os
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

EDGE_FILE = "../disclosure/타법인출자/output/otr_invest_edges_top30.json"


def import_edges():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise RuntimeError(".env 설정오류")

    with open(EDGE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    edges = data.get("edges", [])
    print(f"불러온 edge 수: {len(edges)}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # DB 비우고 새로 넣고 싶으면 이 줄 주석 해제하기
        # session.run("MATCH (n) DETACH DELETE n")

        def _import_edge(tx, edge):
            tx.run(
                """
                MERGE (s:Company {id: $source_id})
                SET  s.name = $source_name

                MERGE (t:Company {id: $target_id})
                SET  t.name = $target_name

                MERGE (s)-[r:INVESTS_IN {id: $edge_id}]->(t)
                SET  r += $props
                """,
                source_id=edge["source"],
                source_name=edge.get("source_name"),
                target_id=edge["target"],
                target_name=edge.get("target_name"),
                edge_id=edge["id"],
                props=edge.get("properties", {}),
            )

        for e in edges:
            session.execute_write(_import_edge, e)

    driver.close()
    print("Neo4j 로 데이터 import 완료!")


if __name__ == "__main__":
    import_edges()
