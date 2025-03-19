import re
import json
import ollama
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import CouchbaseException


def connect_to_cluster(cluster_address, username, password):
    try:
        authenticator = PasswordAuthenticator(username, password)
        cluster = Cluster(f'couchbase://{cluster_address}', ClusterOptions(authenticator))
        
        return cluster
    except CouchbaseException as e:
        print(f"Error connecting to the Couchbase cluster: {e}")
        return None


def extract_test_functions(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        func_pattern = r'^\s*def\s+(test_[a-zA-Z0-9_]*)\s*\('

        test_functions = {}

        for match in re.finditer(func_pattern, content, re.MULTILINE):
            func_name = match.group(1)
            
            start_pos = match.start()
            
            next_def = re.search(r'^\s*def\s+', content[start_pos+1:], re.MULTILINE)
            next_class = re.search(r'^\s*class\s+', content[start_pos+1:], re.MULTILINE)
            
            end_pos = len(content)
            if next_def:
                end_pos = min(end_pos, start_pos + 1 + next_def.start())
            if next_class:
                end_pos = min(end_pos, start_pos + 1 + next_class.start())
            
            # Extract the full function code
            full_match = content[start_pos:end_pos].strip()
            
            # Add to dictionary
            test_functions[func_name] = full_match
            
            print(f"Found function: {func_name}")
        
        # Printing the extracted function names
        print(f"Extracted {len(test_functions)} test functions:", list(test_functions.keys()))
        
        return test_functions
    except Exception as e:
        print(f"Error extracting functions: {e}")
        import traceback
        traceback.print_exc()
        return {}

# Function to get a detailed analysis of a test function using Ollama
def get_test_analysis(function_name, function_code):
    try:
        prompt = f"""
You are an expert Python test analyzer with deep knowledge of testing frameworks and methodologies. Your task is to analyze the following test function and provide a detailed, accurate description of what it does.

Function to analyze:
```python
{function_code}
```

I need you to carefully examine the code and provide:

1. A precise description of what this specific test is verifying
2. The exact sequence of steps this particular test performs, based on the actual code
3. All function calls and dependencies (base functions)used in this specific test
4. The purpose and usage of this test based on its implementation

Your analysis must be based ONLY on the actual code provided, not on general assumptions about testing. Each step should correspond to a specific action in the code.

Return your analysis in this EXACT JSON format (without the "test" wrapper):
{{
  "description": "Detailed description of what this specific test verifies (1-2 sentences)",
  "steps": [
    "Step 1: Specific action from the code",
    "Step 2: Specific action from the code",
    "..."
  ],
  "functions_dependencies": [
    "actual_function_name1",
    "actual_function_name2",
    "..."
  ],
  "usage": "Explanation of how this specific test is used based on its implementation (1-2 sentences)"
}}

IMPORTANT REQUIREMENTS:
1. Each step must correspond to a specific line or block of code in the function
2. Steps must be in the exact order they appear in the code
3. Include ALL function calls made in the test in the functions_dependencies list
4. Be extremely specific about what the test is doing - no generic descriptions
5. If you're unsure about a specific detail, focus on what you can determine from the code
6. Do not include the test function itself in the dependencies list
7. If there are no dependencies, use an empty array []
8. Do not return generic steps - each step should be unique to this specific test
9. Do not wrap the JSON in a "test" object - return the JSON exactly as shown above
"""
        print(f"Prompt: {prompt}")
        model_name = "qwq"
        print(f"Using model: {model_name}")

        try:
            response = ollama.chat(model=model_name, messages=[
                {"role": "user", "content": prompt}
            ])
            result = response['message']['content']
        except (AttributeError, TypeError):
            response = ollama.generate(model=model_name, prompt=prompt)
            result = response['response']
        
        # Try to parse the response as JSON
        try:
            if "```json" in result:
                json_text = result.split("```json")[1].split("```")[0].strip()
                parsed_json = json.loads(json_text)
            elif "```" in result:
                json_text = result.split("```")[1].split("```")[0].strip()
                parsed_json = json.loads(json_text)
            else:
                parsed_json = json.loads(result)
            
            # Wrap in test object if needed
            if "description" in parsed_json and "test" not in parsed_json:
                parsed_json = {"test": parsed_json}
            
            # Validate and fix the structure if needed
            if "test" in parsed_json:
                test_info = parsed_json["test"]
            else:
                # If we don't have the right structure, create it based on what we have
                test_info = {}
                for key in ["description", "steps", "functions_dependencies", "usage"]:
                    if key in parsed_json:
                        test_info[key] = parsed_json[key]
                parsed_json = {"test": test_info}
            
            # Extract function calls from the code if dependencies are missing or empty
            if "functions_dependencies" not in parsed_json["test"] or not parsed_json["test"]["functions_dependencies"]:
                # Extract potential function calls from the code
                self_calls = re.findall(r'self\.([a-zA-Z_][a-zA-Z0-9_]*)\(', function_code)
                regular_calls = re.findall(r'(?<!self\.)([a-zA-Z_][a-zA-Z0-9_]*)\(', function_code)
                
                # Filter out common Python built-ins and keywords
                builtins = ['print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'min', 'max', 
                           'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'any', 'all', 'sum']
                function_calls = [call for call in self_calls + regular_calls 
                                 if call not in builtins 
                                 and not call.startswith('__')
                                 and call != function_name.replace('test_', '')]
                function_calls = list(set(function_calls))  # Remove duplicates
                parsed_json["test"]["functions_dependencies"] = function_calls
            
            # Ensure all required fields exist with meaningful content
            if "description" not in parsed_json["test"] or not parsed_json["test"]["description"]:
                # Extract a meaningful description from the function name and code
                function_purpose = function_name.replace('test_', '').replace('_', ' ')
                
                # Look for assert statements to understand what's being tested
                asserts = re.findall(r'assert\s+([^,;]+)', function_code)
                if asserts:
                    assertion_desc = ", ".join(asserts[:2])  # Take first two assertions
                    parsed_json["test"]["description"] = f"This test verifies {function_purpose} by asserting {assertion_desc}."
                else:
                    parsed_json["test"]["description"] = f"This test verifies the behavior of {function_purpose}."
            
            # Ensure steps are detailed and specific
            if "steps" not in parsed_json["test"] or not parsed_json["test"]["steps"] or len(parsed_json["test"]["steps"]) < 3:
                # Extract steps from the code by analyzing function calls and control structures
                steps = []
                
                # Look for setup/initialization
                setup_calls = re.findall(r'self\.(setup|setUp|initialize|init|create|load|prepare)[a-zA-Z_]*\(', function_code)
                if setup_calls:
                    steps.append(f"Initialize test by calling {', '.join(setup_calls)}.")
                else:
                    steps.append("Set up test prerequisites and environment.")
                
                # Look for main operations
                main_calls = re.findall(r'self\.([a-zA-Z_][a-zA-Z0-9_]*)\(', function_code)
                main_calls = [call for call in main_calls if call not in ['setUp', 'tearDown', 'assert', 'fail']]
                
                for call in main_calls[:5]:  # Limit to first 5 calls to avoid too many steps
                    steps.append(f"Execute {call.replace('_', ' ')}.")
                
                # Look for assertions
                assertions = re.findall(r'(assert[A-Za-z]*|self\.assert[A-Za-z]*)\s*\(', function_code)
                if assertions:
                    steps.append(f"Verify results using {len(assertions)} assertions.")
                
                # Look for cleanup
                cleanup_calls = re.findall(r'self\.(tearDown|cleanup|clean_up|delete|remove)[a-zA-Z_]*\(', function_code)
                if cleanup_calls:
                    steps.append(f"Clean up resources by calling {', '.join(cleanup_calls)}.")
                
                parsed_json["test"]["steps"] = steps
            
            if "usage" not in parsed_json["test"] or not parsed_json["test"]["usage"]:
                # Generate usage based on function name and code
                function_purpose = function_name.replace('test_', '').replace('_', ' ')
                
                # Look for comments that might indicate purpose
                comments = re.findall(r'#\s*(.*?)$', function_code, re.MULTILINE)
                if comments:
                    parsed_json["test"]["usage"] = f"This test is used to {comments[0].strip().lower()}."
                else:
                    parsed_json["test"]["usage"] = f"This test ensures correct behavior when {function_purpose}."
            
            return parsed_json
            
        except json.JSONDecodeError:
            print(f"Warning: Could not parse response as JSON. Creating a structured analysis.")
            # Extract function purpose from name
            function_purpose = function_name.replace('test_', '').replace('_', ' ')
            
            # Extract potential function calls from the code
            self_calls = re.findall(r'self\.([a-zA-Z_][a-zA-Z0-9_]*)\(', function_code)
            regular_calls = re.findall(r'(?<!self\.)([a-zA-Z_][a-zA-Z0-9_]*)\(', function_code)
            
            # Filter out common Python built-ins and keywords
            builtins = ['print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'min', 'max']
            function_calls = [call for call in self_calls + regular_calls if call not in builtins and not call.startswith('__')]
            function_calls = list(set(function_calls))  # Remove duplicates
            
            # Extract specific steps from the code
            steps = []
            
            # Look for setup/initialization
            setup_calls = [call for call in self_calls if any(prefix in call for prefix in ['setup', 'setUp', 'initialize', 'init', 'create', 'load', 'prepare'])]
            if setup_calls:
                steps.append(f"Initialize test environment by calling {', '.join(setup_calls)}.")
            else:
                steps.append("Set up test prerequisites and environment.")
            
            # Look for main operations
            main_calls = [call for call in self_calls if call not in ['setUp', 'tearDown', 'assert', 'fail'] and call not in setup_calls]
            for call in main_calls[:5]:  # Limit to first 5 calls to avoid too many steps
                steps.append(f"Execute {call.replace('_', ' ')}.")
            
            # Look for assertions
            assertions = re.findall(r'(assert[A-Za-z]*|self\.assert[A-Za-z]*)\s*\(', function_code)
            if assertions:
                steps.append(f"Verify results using {len(assertions)} assertions.")
            
            # Look for cleanup
            cleanup_calls = [call for call in self_calls if any(prefix in call for prefix in ['tearDown', 'cleanup', 'clean_up', 'delete', 'remove'])]
            if cleanup_calls:
                steps.append(f"Clean up resources by calling {', '.join(cleanup_calls)}.")
            
            # Create a structured analysis
            return {
                "test": {
                    "description": f"This test verifies the behavior when {function_purpose}.",
                    "steps": steps,
                    "functions_dependencies": function_calls,
                    "usage": f"This test ensures that the system correctly handles scenarios involving {function_purpose}."
                }
            }
    
    except Exception as e:
        print(f"Error with Ollama: {e}")
        # Create a basic analysis based on the function name and code
        function_words = function_name.replace('test_', '').split('_')

        try:
            self_calls = re.findall(r'self\.([a-zA-Z_][a-zA-Z0-9_]*)\(', function_code)
            regular_calls = re.findall(r'(?<!self\.)([a-zA-Z_][a-zA-Z0-9_]*)\(', function_code)
            builtins = ['print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'min', 'max']
            function_calls = [call for call in self_calls + regular_calls if call not in builtins and not call.startswith('__')]
            function_calls = list(set(function_calls))  # Remove duplicates
        except:
            function_calls = []
        
        # Extract steps from code even in case of error
        try:
            steps = []
            # Look for setup/initialization
            setup_calls = [call for call in self_calls if any(prefix in call for prefix in ['setup', 'setUp', 'initialize', 'init', 'create', 'load', 'prepare'])]
            if setup_calls:
                steps.append(f"Initialize test by calling {', '.join(setup_calls)}.")
            else:
                steps.append("Set up test prerequisites.")
            
            # Look for main operations
            main_calls = [call for call in self_calls if call not in ['setUp', 'tearDown', 'assert', 'fail'] and call not in setup_calls]
            for call in main_calls[:3]:  # Limit to first 3 calls
                steps.append(f"Execute {call.replace('_', ' ')}.")
            
            # Look for assertions
            assertions = re.findall(r'(assert[A-Za-z]*|self\.assert[A-Za-z]*)\s*\(', function_code)
            if assertions:
                steps.append(f"Verify results using assertions.")
            
            # Look for cleanup
            cleanup_calls = [call for call in self_calls if any(prefix in call for prefix in ['tearDown', 'cleanup', 'clean_up', 'delete', 'remove'])]
            if cleanup_calls:
                steps.append(f"Clean up resources.")
        except:
            steps = [
                "Set up test prerequisites",
                f"Execute operations related to {' '.join(function_words)}",
                "Verify expected results",
                "Clean up test resources"
            ]
        
        return {
            "test": {
                "description": f"This test verifies the behavior of {' '.join(function_words)}.",
                "steps": steps,
                "functions_dependencies": function_calls,
                "usage": f"This test ensures that the system correctly handles {' '.join(function_words)} scenarios."
            }
        }


def store_document(cluster, bucket_name, doc_id, doc_content):
    try:
        bucket = cluster.bucket(bucket_name)

        collection = bucket.default_collection()

        result = collection.upsert(doc_id, doc_content)
        
        print(f"Document with ID '{doc_id}' stored successfully.")
        # Print a preview of the stored document
        if isinstance(doc_content, dict) and "test" in doc_content:
            test_info = doc_content["test"]
            print(f"Description: {test_info.get('description', 'N/A')}")
            print(f"Steps: {len(test_info.get('steps', []))} steps included")
            deps = test_info.get('functions_dependencies', [])
            print(f"Dependencies: {', '.join(deps) if deps else 'None'}")
    except CouchbaseException as e:
        print(f"Error storing the document: {e}")


if __name__ == '__main__':
    # Parameters
    cluster_address = '192.168.64.23:8091'  
    username = 'Administrator'     
    password = 'password'         
    bucket_name = 'test'       
    file_path = 'test_file.py'  


    cluster = connect_to_cluster(cluster_address, username, password)
    
    if cluster:
        test_functions = extract_test_functions(file_path)
        
        if not test_functions:
            print("No test functions found in the file. Exiting.")
        else:
            for func_name, func_code in test_functions.items():
                print(f"\nProcessing test function: {func_name}")

                test_analysis = get_test_analysis(func_name, func_code)
                
                if test_analysis:
                    store_document(cluster, bucket_name, func_name, test_analysis)
                else:
                    print(f"Skipping function {func_name} due to missing analysis output.")
            
            print("\nProcessing complete.")