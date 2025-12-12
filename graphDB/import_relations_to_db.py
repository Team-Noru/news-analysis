import os
import csv
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

NODE_FILE = "graph_nodes.csv"
EDGE_FILE = "graph_edges.csv"
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# node import
def import_nodes():

    with driver.session() as session:
        with open(NODE_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                session.run(
                    """
                    MERGE (n:Entity {id: $node_id})
                    SET n.name = $name,
                        n.entity_type = $entity_type,
                        n.corp_code = $corp_code,
                        n.market = $market,
                        n.cap_bucket = $cap_bucket,
                        n.market_cap_eok = $market_cap
                    """,
                    node_id=row["node_id"],
                    name=row["name"],
                    entity_type=row["entity_type"],
                    corp_code=row["corp_code"],
                    market=row["market"],
                    cap_bucket=row["cap_bucket"],
                    market_cap=row["market_cap_unit_eok_krw"] or None,
                )



# edge import
def import_edges():

    with driver.session() as session:
        with open(EDGE_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                session.run(
                    """
                    MATCH (s:Entity {id: $from_id})
                    MATCH (t:Entity {id: $to_id})

                    MERGE (s)-[r:RELATION {
                        id: $edge_id
                    }]->(t)

                    SET r.rel_type = $rel_type,
                        r.event_type = $event_type,
                        r.event_tag = $event_tag,
                        r.event_date = $event_date,
                        r.rcept_no = $rcept_no,
                        r.weight = $weight,
                        r.source_json = $source_json,
                        r.extra_json = $extra_json
                    """,
                    edge_id=row["edge_id"],
                    from_id=row["from_id"],
                    to_id=row["to_id"],
                    rel_type=row["rel_type"],
                    event_type=row["event_type"],
                    event_tag=row["event_tag"],
                    event_date=row["event_date"],
                    rcept_no=row["rcept_no"],
                    weight=row["weight"] or None,
                    source_json=row["source_json"],
                    extra_json=row["extra_json"],
                )



# 실행
def main():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise RuntimeError(".env에 NEO4J_URI / USER / PASSWORD가 없습니다!")

    import_nodes()
    import_edges()

    print("모든 데이터 Import 완료!")
    driver.close()


if __name__ == "__main__":
    main()
