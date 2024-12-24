import json
import pandas as pd
from neo4j import GraphDatabase
from scripts.graph_neo4j import create_nodes_and_relationships, driver, graph
from scripts.inpatient import process, process_revenue

demo_records = pd.read_csv('demo.csv')
charges_df = pd.read_csv('charges.csv')

# Function to read JSON from a file
def read_json_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Path to your JSON file
contract_file_path = r'C:\Users\USER\HRA-POC\data\BILH Cigna Inpatient Paid in Addition.json'
cigna_implant_codes = [274, 275, 278, 276]
# Read the JSON data from the file
contract_data = read_json_file(contract_file_path)

def upload_json_on_graph(contract_data):
    create_nodes_and_relationships(contract_data)

#call if required to upload json data in graph db
# upload_json_on_graph(contract_data)

graph.refresh_schema()
print(graph.schema)
output_records = []
#Iterate or loop each demo records from demo.csv 
for _, demodata in demo_records.iterrows():
    # Assuming 'demodata' is a pandas Series, and 'encounterid' is a column in the CSV
    service_date_from = pd.to_datetime(demodata['ServiceDateFrom'])
    service_date_to = pd.to_datetime(demodata['ServiceDateTo'])
    
    # Find rows in charges_df matching the encounter ID
    matching_charges = charges_df[charges_df['EncounterID'] == demodata['EncounterID']]
     # Check if any revenue code matches the Cigna revenue list
    matching_rows = matching_charges[matching_charges['RevenueCode'].isin(cigna_implant_codes)]
    lengthOfStay = (service_date_to - service_date_from).days
    amount = process(graph, demodata, lengthOfStay)
    output = {
        "encounterid": demodata["EncounterID"], 
        "drg_code": demodata["DRG"],
        "calculatedprice": amount
    }
    output_records.append(output)
    print(matching_rows)
    for _, chargesdata in matching_rows.iterrows():
        revenue_amount = process_revenue(graph, chargesdata)
        print(revenue_amount)
        output = {
        "encounterid": demodata["EncounterID"], 
        "revenue_code":chargesdata["RevenueCode"],
        "calculatedprice": revenue_amount+amount
        }
     # Append the output to the list
        output_records.append(output)

# After processing all demo records, write the results to a JSON file
with open('output_file.json', 'w') as json_file:
    json.dump(output_records, json_file, indent=4)

driver.close()