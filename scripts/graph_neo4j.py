import json
from neo4j import GraphDatabase
from langchain_community.graphs import Neo4jGraph
# Neo4j connection setup
uri = "neo4j+ssc://72eb88b7.databases.neo4j.io"  # Neo4j connection URI
username = "neo4j"  # Neo4j username
password = "SMNuPBsCh_G488jcmlvkUv2AE9ID5XLm2Rvv126O2Pg"  # Neo4j password

# Initialize the Neo4j driver
driver = GraphDatabase.driver(uri, auth=(username, password))

graph=Neo4jGraph(
    url=uri,
    username=username,
    password=password,
)


# Function to create nodes and relationships
def create_nodes_and_relationships(json_data):
    with driver.session() as session:
        for record in json_data:
            service_name = record.get("Service", "Unknown Service")

            # Create a 'Service' node
            session.run("MERGE (s:Service {name: $service_name})", service_name=service_name)

            # Create other nodes based on the keys in the JSON record
            for key, value in record.items():
                if key != "Service":  # Skip Service as it's already handled
                    node_label = key.replace(" ", "_")  # Convert spaces to underscores for node labels

                    # Check if the value is a comma-separated string (e.g., Revenue Code)
                    if isinstance(value, str) and "," in value:
                        # Split the value by commas
                        items = value.split(", ")
                        for item in items:
                            # Create a node for each item and link it to the Service
                            session.run(f"MERGE (n:{node_label} {{value: $item}})", item=item)
                            session.run(
                                f"""
                                MATCH (s:Service {{name: $service_name}}), (n:{node_label} {{value: $item}})
                                MERGE (s)-[:HAS_{node_label.upper()}]->(n)
                                """, service_name=service_name, item=item)
                    # If the value is a string (not a list or comma-separated), create a node for it
                    elif isinstance(value, str):
                        session.run(f"MERGE (n:{node_label} {{value: $value}})", value=value)
                        session.run(
                            f"""
                            MATCH (s:Service {{name: $service_name}}), (n:{node_label} {{value: $value}})
                            MERGE (s)-[:HAS_{node_label.upper()}]->(n)
                            """, service_name=service_name, value=value)
                    # If the value is a list (like Revenue Code values), create nodes for each item and link them
                    elif isinstance(value, list):
                        for item in value:
                            session.run(f"MERGE (n:{node_label} {{value: $item}})", item=item)
                            session.run(
                                f"""
                                MATCH (s:Service {{name: $service_name}}), (n:{node_label} {{value: $item}})
                                MERGE (s)-[:HAS_{node_label.upper()}]->(n)
                                """, service_name=service_name, item=item)
                    # If the value is a number (float or integer), create a node for it
                    elif isinstance(value, (int, float)):
                        session.run(f"MERGE (n:{node_label} {{value: $value}})", value=value)
                        session.run(
                            f"""
                            MATCH (s:Service {{name: $service_name}}), (n:{node_label} {{value: $value}})
                            MERGE (s)-[:HAS_{node_label.upper()}]->(n)
                            """, service_name=service_name, value=value)
                        
# Function to retrieve the graph data and store it in a variable
def fetch_graph_data():
    with driver.session() as session:
        result = session.run("MATCH (n)-[r]->(m) RETURN n, r, m")
        graph_data = []
        for record in result:
            graph_data.append({
                "source": {
                    "id": record["n"].id,
                    "labels": list(record["n"].labels),
                    "properties": dict(record["n"])
                },
                "relationship": {
                    "type": record["r"].type,
                    "properties": dict(record["r"])
                },
                "target": {
                    "id": record["m"].id,
                    "labels": list(record["m"].labels),
                    "properties": dict(record["m"])
                }
            })
        
        # Convert graph data to a properly formatted JSON string
        formatted_graph_data = json.dumps(graph_data, indent=4)
        
        return formatted_graph_data