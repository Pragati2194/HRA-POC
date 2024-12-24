from scripts.graph_neo4j import driver, graph
from langchain.chains import GraphCypherQAChain
from scripts.openai_setup import llm

def process(graph, claimObject, lengthOfStay):
    """
    Processes the claim object to calculate rates based on DRG code.
    Handles multiple records returned from the query.
    """
    drg_code = str(claimObject.get('DRG'))
    print(drg_code)
    if not drg_code:
        raise ValueError("DRG code is missing in the claim object")

    # Query the graph for DRG code
    graph_objects = query_drg_code(drg_code)  # Expecting a list of results
    print(graph_objects)

    if not graph_objects or "error" in graph_objects[0]:
        # Handle case where no valid records are found
        return {"error": f"No valid data found for DRG code: {drg_code}"}

    # Prepare to process multiple records
    results = []
    for graph_object in graph_objects:
        rule_type = graph_object.get('Rule')

        # Define processing logic based on rule type
        switch_case = {
            "Case Rate": lambda: calculate_case_rate(graph_object, lengthOfStay),
            "Per Diem": lambda: calculate_per_diem(graph_object, lengthOfStay),
            "default": lambda: {"error": f"Unknown rule type: {rule_type}"}
        }

        # Process the record and append the result
        result = switch_case.get(rule_type, switch_case["default"])()

    # Return all processed results
    return result

def process_revenue(graph, claimObject):
    revenue_code = str(int(float(claimObject.get('RevenueCode'))))
    print(revenue_code)
    if not revenue_code:
        raise ValueError("revenue code is missing in the claim object")

    # Query the graph for DRG code
    graph_objects = query_revenue_code(revenue_code)
    # graph_objects = dynamic_query_revenue_code(revenue_code)
    print(graph_objects)
    results = []
    for graph_object in graph_objects:
        rule_type = graph_object.get('Rule')
        # Define processing logic based on rule type
        switch_case = {
            "50% Reduction from Billed Charges": lambda: Reduction_from_Billed_Charges(graph_object, claimObject.get('Amount')),
            "default": lambda: {"error": f"Unknown rule type: {rule_type}"}
        }
        result = switch_case.get(rule_type, switch_case["default"])()
        # results.append(result)

    # Return all processed results
    return result

def query_revenue_code(revenue_code):
    # Use a session inside the context manager to ensure proper cleanup
    with driver.session() as session:
        # Cypher query to check for Revenue Code, Rule, Rate, Note, Procedure Code, and Threshold Limit
        cypher_query = """
        MATCH (s:Service)-[:HAS_REVENUE_CODE]->(rc:Revenue_Code {value: $revenue_code})
        OPTIONAL MATCH (s)-[:HAS_RULE]->(ru:Rule)
        OPTIONAL MATCH (s)-[:HAS_RATE]->(ra:Rate)
        OPTIONAL MATCH (s)-[:HAS_NOTE]->(no:Note)
        OPTIONAL MATCH (s)-[:HAS_PROCEDURE_CODE]->(pc:Procedure_Code)
        OPTIONAL MATCH (s)-[:HAS_THRESHOLD_LIMIT]->(tl:Threshold_Limit)
        
        RETURN 
            rc IS NOT NULL AS REVENUE_Code_Found,
            ru IS NOT NULL AS Rule_Found,
            ra IS NOT NULL AS Rate_Found,
            no IS NOT NULL AS Note_Found,
            pc IS NOT NULL AS Procedure_Code_Found,
            tl IS NOT NULL AS THRESHOLD_LIMIT_Found,
            COALESCE(ru.value, "Not Found") AS Rule,
            COALESCE(ra.value, "Not Found") AS Rate,
            COALESCE(no.value, "Not Found") AS Note,
            COALESCE(pc.value, "Not Found") AS Procedure_Code,
            COALESCE(tl.value, "Not Found") AS THRESHOLD_LIMIT
        """
        # Execute the query with the Revenue code parameter
        result = session.run(cypher_query, revenue_code=revenue_code)
        
        # Collect all matching records into a list
        records = [record.data() for record in result]
        print(records)
        
        if records:
            return records  # Return a list of all results
        else:
            return [{"error": "No data found for the specified Revenue code."}]



def dynamic_query_revenue_code(revenue_code):
    chain = GraphCypherQAChain.from_llm(llm=llm, graph=graph, verbose=True, allow_dangerous_requests=True)
    
    # Pass the drg_code as part of the query
    query_string = f"give rule, threshold rate for revenue code {revenue_code} in a json format"
    response = chain.invoke({"query": query_string})
    # Access the 'result' key and split it to extract the values
    result_string = response.get('result', '')

    # Extract Rule and Rate from the descriptive result string
    if "rule for DRG code" in result_string:
        import re
        match = re.search(r"'(.+?)' and the threshold rate is ([\d.]+)", result_string)
        if match:
            result = {'Rule': match.group(1), 'Rate': match.group(2)}
            return result
        else:
            print("Failed to extract Rule and Rate.")
    else:
        print("Unexpected result format:", result_string)

# def query_drg_code(drg_code_value):
#     # Use a session inside the context manager to ensure proper cleanup
#     with driver.session() as session:
#         # Cypher query to fetch Rule and Rate for the given DRG code
#         cypher_query = """
#         MATCH (s:Service)-[:HAS_MS_DRG_CODES]->(d:MS_DRG_Codes {value: $drg_code})
#         MATCH (s)-[:HAS_RULE]->(r:Rule)
#         MATCH (s)-[:HAS_RATE]->(rate:Rate)
#         RETURN {Rule: trim(r.value), Rate: rate.value} AS Result
#         """
#         # Execute the query with the DRG code parameter
#         result = session.run(cypher_query, drg_code=drg_code_value)
    
#         # Process the result and return it as a dictionary
#         record = result.single()  # Only expecting one result
#         if record:
#             return record["Result"]
#         else:
#             return {"error": "No data found for the specified DRG code."}

def query_drg_code(drg_code_value):
    # Use a session inside the context manager to ensure proper cleanup
    with driver.session() as session:
        # Cypher query to check for MS_DRG_Code, Outlier entities, Rule, and Rate
        cypher_query = """
        MATCH (s:Service)-[:HAS_MS_DRG_CODE]->(ms:MS_DRG_Code {value: $drg_code})
        OPTIONAL MATCH (s)-[:HAS_OUTLIER_DAYS]->(od:Outlier_Days)
        OPTIONAL MATCH (s)-[:HAS_OUTLIER_RATE]->(or:Outlier_Rate)
        OPTIONAL MATCH (s)-[:HAS_OUTLIER_RULE]->(ou:Outlier_Rule)
        OPTIONAL MATCH (s)-[:HAS_RULE]->(rule:Rule)
        OPTIONAL MATCH (s)-[:HAS_RATE]->(rate:Rate)
        
        RETURN {
            MS_DRG_Code_Found: ms IS NOT NULL,
            Outlier_Days_Found: od IS NOT NULL,
            Outlier_Rate_Found: or IS NOT NULL,
            Outlier_Rule_Found: ou IS NOT NULL,
            Rule_Found: rule IS NOT NULL,
            Rate_Found: rate IS NOT NULL,
            Outlier_Days: CASE WHEN od IS NOT NULL THEN od.value ELSE "Not Found" END,
            Outlier_Rate: CASE WHEN or IS NOT NULL THEN or.value ELSE "Not Found" END,
            Outlier_Rule: CASE WHEN ou IS NOT NULL THEN ou.value ELSE "Not Found" END,
            Rule: CASE WHEN rule IS NOT NULL THEN trim(rule.value) ELSE "Not Found" END,
            Rate: CASE WHEN rate IS NOT NULL THEN rate.value ELSE "Not Found" END
        } AS Result
        """
        # Execute the query with the DRG code parameter
        result = session.run(cypher_query, drg_code=drg_code_value)
    
        # Collect all matching records into a list
        records = [record["Result"] for record in result]
        if records:
            return records  # Return a list of all results
        else:
            return [{"error": "No data found for the specified DRG code."}]


def calculate_num_of_days_stay():
    return 4

def Reduction_from_Billed_Charges(graph_object, amount):
    # Calculate 50% of the amount
    reduced_amount = amount * 0.5
    
    # Get the threshold limit from the graph_object
    threshold_limit_str = graph_object.get('THRESHOLD_LIMIT')
    # Check if the threshold_limit_str is not None or empty
    if threshold_limit_str is None or threshold_limit_str == "":
        raise ValueError("Threshold Limit is missing or invalid in the graph_object.")
    
    # Remove the dollar sign and commas, and convert to float
    try:
        threshold_limit = float(threshold_limit_str.replace('$', '').replace(',', ''))
    except ValueError:
        raise ValueError(f"Invalid Threshold Limit value: {threshold_limit_str}")
    
    # Compare reduced amount with the threshold limit
    if threshold_limit < reduced_amount:
        return threshold_limit
    else:
        return reduced_amount


def calculate_case_rate(graph_return_obj, stay):
    try:
        # Safely extract and process the 'Rate' value
        rate_str = graph_return_obj.get('Rate', 0)
        if isinstance(rate_str, str):
            # Remove any trailing or extraneous characters and convert to float
            amount = float(rate_str.strip('.'))
        else:
            amount = float(rate_str)

        # Safely process Outlier_Days and Outlier_Rate if both are present
        outlier_days = graph_return_obj.get('Outlier_Days', 'Not Found')
        outlier_rate = graph_return_obj.get('Outlier_Rate', 'Not Found')

        # Use the calculate_outlier_rate function to handle outlier logic
        return calculate_outlier_rate(outlier_days, outlier_rate, stay, amount)

    except (ValueError, TypeError) as e:
        print(f"Error in calculate_case_rate: {e}")
        return 0.0

def calculate_outlier_rate(outlier_days, outlier_rate, stay, amount):
    """Calculates the adjusted rate based on outlier days and outlier rate."""
    if outlier_days != 'Not Found' and outlier_rate != 'Not Found':
        try:
            # Ensure Outlier_Rate is a float and Outlier_Days is an integer
            outlier_rate = float(outlier_rate)
            outlier_days = int(outlier_days)

            # Apply outlier logic if stay is greater than or equal to outlier_days
            if stay >= outlier_days:
                return amount + abs(stay - outlier_days) * outlier_rate
        except (ValueError, TypeError):
            # Return amount if there's any issue with conversion
            return amount
    return amount



def calculate_per_diem(graph_return_obj, stay):
    # Safely extract and process the 'Rate' value
    rate_str = graph_return_obj.get('Rate', 0)
    try:
        # Remove any trailing or extraneous characters like '.' and convert to float
        if isinstance(rate_str, str):
            rate = float(rate_str.strip('.'))
        else:
            rate = float(rate_str)
    except ValueError:
        # Default to 0.0 if conversion fails
        rate = 0.0
    
    # Calculate the per diem
    per_diem = rate * stay
    return per_diem

def calculate_pay_inaddition(amount, graph_return_obj):
    final_amount = amount + (amount % graph_return_obj.pay_inaddtion_rate)
    return final_amount
# def checkForPayInAdditionReturnObject():
#     #need to get this object from graph
#     return