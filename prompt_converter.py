import xmltodict
import yaml
import os

def xml_to_yaml(input_file):
    """Convert XML file to YAML file while preserving structure."""
    # Generate output filename by replacing .xml with .yaml
    output_file = input_file.replace('.xml', '.yaml')
    with open(input_file, 'r') as xml_file:
        xml_string = xml_file.read()
    try:
        # Try to parse XML to dictionary
        xml_dict = xmltodict.parse(xml_string)
    except Exception as e:
        print(f"XML parsing error: {str(e)}")
        print("Attempting to fix the XML structure...")
        # Try to fix common XML issues
        # 1. Wrap everything in a root element if missing
        fixed_xml = f"<root>\n{xml_string}\n</root>"
        try:
            xml_dict = xmltodict.parse(fixed_xml)
            print("Successfully parsed XML after adding root element.")
        except Exception as e2:
            print(f"Failed to fix XML: {str(e2)}")
            print("Please check if your XML file is well-formed.")
            return None
    # Convert to YAML with proper formatting
    yaml_string = yaml.dump(xml_dict, default_flow_style=False, sort_keys=False)
    with open(output_file, 'w') as yaml_file:
        yaml_file.write(yaml_string)
    return output_file
def yaml_to_xml(input_file):
    """Convert YAML file to XML file while preserving structure."""
    # Generate output filename by replacing .yaml with .xml
    output_file = input_file.replace('.yaml', '.xml')
    with open(input_file, 'r') as yaml_file:
        yaml_string = yaml_file.read()
    # Parse YAML to dictionary
    yaml_dict = yaml.safe_load(yaml_string)
    # Convert to XML with proper formatting
    xml_string = xmltodict.unparse(yaml_dict, pretty=True)
    with open(output_file, 'w') as xml_file:
        xml_file.write(xml_string)
    return output_file

def process_directory(input_dir, conversion_type):
    """Process all files in a directory for conversion."""
    converted_files = []
    for filename in os.listdir(input_dir):
        input_path = os.path.join(input_dir, filename)
        # Skip directories
        if os.path.isdir(input_path):
            continue
        if conversion_type == 'xml_to_yaml' and filename.endswith('.xml'):
            output_path = xml_to_yaml(input_path)
            converted_files.append((input_path, output_path))
            print(f"Converted {input_path} to {output_path}")
        elif conversion_type == 'yaml_to_xml' and filename.endswith('.yaml'):
            output_path = yaml_to_xml(input_path)
            converted_files.append((input_path, output_path))
            print(f"Converted {input_path} to {output_path}")
    return converted_files

if __name__ == "__main__":
    print("XML-YAML Converter")
    print("1. Convert single file")
    print("2. Convert all files in directory")
    choice = input("Enter your choice (1/2): ").strip()
    if choice == '1':
        input_file = input("Enter input file path: ").strip()
        if not os.path.exists(input_file):
            print(f"Error: File {input_file} does not exist.")
        elif input_file.endswith('.xml'):
            output_file = xml_to_yaml(input_file)
            print(f"Converted {input_file} to {output_file}")
        elif input_file.endswith('.yaml'):
            output_file = yaml_to_xml(input_file)
            print(f"Converted {input_file} to {output_file}")
        else:
            print("Invalid file extension. Please provide a .xml or .yaml file.")
    elif choice == '2':
        input_dir = input("Enter input directory: ").strip()
        if not os.path.exists(input_dir) or not os.path.isdir(input_dir):
            print(f"Error: Directory {input_dir} does not exist.")
        else:
            print("1. Convert XML to YAML")
            print("2. Convert YAML to XML")
            conversion_choice = input("Enter your choice (1/2): ").strip()
            if conversion_choice == '1':
                converted_files = process_directory(input_dir, 'xml_to_yaml')
                print(f"Converted {len(converted_files)} XML files to YAML.")
            elif conversion_choice == '2':
                converted_files = process_directory(input_dir, 'yaml_to_xml')
                print(f"Converted {len(converted_files)} YAML files to XML.")
            else:
                print("Invalid choice. Please enter 1 or 2.")
    else:
        print("Invalid choice. Please enter 1 or 2.")