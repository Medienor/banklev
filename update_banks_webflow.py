import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import unicodedata
import re

# Define the mapping between XML <f:...> fields and Webflow fieldData fields
field_mapping = {
    'bb_adresse1': 'f-bb-adresse1',
    'bb_epost': 'f-bb-epost',
    'bb_postnr': 'f-bb-postnr',
    'bb_poststed': 'f-bb-poststed',
    'bb_telefon': 'f-bb-telefon',
    'marked_boliglan': 'f-marked-boliglan',
    'marked_boliglan_info': 'f-marked-boliglan-info-2',
    'marked_generell': 'f-marked-generell',
    'marked_generell_info': 'f-marked-generell-info-2',
    'orgnr': 'f-orgnr',
    'tilbyr_banksparing': 'f-tilbyr-banksparing',
    'tilbyr_boliglan': 'f-tilbyr-boliglan',
    'tilbyr_dagligbank': 'f-tilbyr-dagligbank',
    'tilbyr_forbrukslan': 'f-tilbyr-forbrukslan',
    'tilbyr_kredittkort': 'f-tilbyr-kredittkort',
    'tilbyr_sph': 'f-tilbyr-sph',
    'url': 'f-url'
}

# Function to normalize string for slug
def normalize_for_slug(text):
    if not text:
        return ''
    
    # Replace special characters and normalize unicode
    text = text.replace('æ', 'a').replace('ø', 'o').replace('å', 'a')
    normalized_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    
    # Remove parentheses from text
    normalized_text = normalized_text.replace('(', '').replace(')', '')
    
    # Replace dots with dashes
    normalized_text = normalized_text.replace('.', '-')
    
    # Remove commas, colons, and ampersands
    normalized_text = re.sub(r'[,:&]', '', normalized_text)
    
    # Replace slashes with dashes
    normalized_text = normalized_text.replace('/', '-')
    
    # Replace spaces with dashes and convert to lowercase
    slug = '-'.join(normalized_text.lower().strip().split())
    
    return slug

# Function to parse XML and extract data
def parse_xml_and_process():
    # Define the URL and credentials for the XML API
    xml_url = "https://www.finansportalen.no/services/feed/v3/bank/bankleverandor.atom"
    username = "feeduser_eines"
    password = "Jo21iaejo21iae!"

    session = requests.Session()
    session.auth = (username, password)
    response = session.get(xml_url)

    if response.status_code == 200:
        root = ET.fromstring(response.content)
        
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'f': 'http://www.finansportalen.no/feed/ns/1.0'
        }
        
        # List to store entries from XML
        xml_entries = []
        
        for entry in root.findall('atom:entry', namespaces):
            title = entry.find('atom:title', namespaces).text.strip()
            orgnr = entry.find('f:orgnr', namespaces).text.strip()
            
            # Extracting fieldData equivalents from XML
            xml_data = {}
            for elem in entry.findall('f:*', namespaces):
                tag = elem.tag.split('}')[1]
                xml_data[tag] = elem.text.strip() if elem.text else ''
            
            # Generate slug from title
            slug = normalize_for_slug(title)
            
            # Store the title, orgnr, and XML fieldData in a tuple
            xml_entries.append((title, orgnr, xml_data, slug))
        
        # Call function to check existence and compare fields in Webflow
        check_webflow_existence(xml_entries)


def check_webflow_existence(xml_entries):
    url_base = "https://api.webflow.com/v2/collections/66636a29a268f18ba1798b0a/items"
    limit = 100
    total_items = []

    headers = {
        "accept": "application/json",
        "authorization": "Bearer 523387bf0364a9730be88b71624f85cdd556ea24b561eefcf2f7d67fa1447c30"
    }

    offset = 0
    while offset <= 900:
        url = f"{url_base}?limit={limit}&offset={offset}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            total_items.extend(items)
            offset += limit  # Move to the next set of items
        else:
            print(f"Failed to retrieve data for offset {offset}. Status code: {response.status_code}")
            break
    
    # Print total number of items in Webflow CMS
    cms_count = len(total_items)
    print(f"Total number of items in Finansportalen XML: {len(xml_entries)}")
    print(f"Total number of items in Webflow CMS: {cms_count}")

    # Iterate over each XML entry and find the corresponding Webflow item
    for title, orgnr, xml_data, slug in xml_entries:
        mismatch_fields = []
        
        # Search for the corresponding Webflow item using the 'name' field
        webflow_item = None
        for item in total_items:
            if 'fieldData' in item and 'name' in item['fieldData'] and item['fieldData']['name'] == title:
                webflow_item = item
                break
        
        if webflow_item:
            update_payload = {
                "isArchived": False,
                "isDraft": False,
                "fieldData": {}  # Initialize fieldData dictionary for update
            }
            
            # Update all mapped fields from xml_data to update_payload
            for xml_field, webflow_field in field_mapping.items():
                if xml_field in xml_data:
                    update_payload['fieldData'][webflow_field] = xml_data[xml_field]
            
            # Assuming 'name' and 'slug' are always updated
            update_payload['fieldData']['name'] = title
            update_payload['fieldData']['slug'] = slug
            
            # Update Webflow item
            update_webflow_item(webflow_item['id'], update_payload)
            
        else:
            # Item does not exist in Webflow, create new item if needed
            print(f"Creating new item for {title} ({orgnr}) in Webflow.")
            create_webflow_item(title, orgnr, xml_data, slug)


def update_webflow_item(item_id, payload):
    url_base = f"https://api.webflow.com/v2/collections/66636a29a268f18ba1798b0a/items/{item_id}/live"
    headers = {
        "accept": "application/json",
        "authorization": "Bearer 523387bf0364a9730be88b71624f85cdd556ea24b561eefcf2f7d67fa1447c30",
        "Content-Type": "application/json"
    }
    
    response = requests.patch(url_base, json=payload, headers=headers)
    if response.status_code == 200:
        print(f"Successfully updated item with ID {item_id} in Webflow.")
    else:
        print(f"Failed to update item with ID {item_id} in Webflow. Status code: {response.status_code}")
        print(f"Error message: {response.json()}")


def create_webflow_item(title, orgnr, xml_data, slug):
    url_base = "https://api.webflow.com/v2/collections/66636a29a268f18ba1798b0a/items/live"
    headers = {
        "accept": "application/json",
        "authorization": "Bearer 523387bf0364a9730be88b71624f85cdd556ea24b561eefcf2f7d67fa1447c30",
        "Content-Type": "application/json"
    }
    
    # Create the fieldData payload using the field_mapping
    field_data = {
        field_mapping['tilbyr_kredittkort']: xml_data.get('tilbyr_kredittkort', ''),
        field_mapping['tilbyr_sph']: xml_data.get('tilbyr_sph', ''),
        field_mapping['tilbyr_forbrukslan']: xml_data.get('tilbyr_forbrukslan', ''),
        field_mapping['tilbyr_banksparing']: xml_data.get('tilbyr_banksparing', ''),
        field_mapping['tilbyr_dagligbank']: xml_data.get('tilbyr_dagligbank', ''),
        field_mapping['tilbyr_boliglan']: xml_data.get('tilbyr_boliglan', ''),
        field_mapping['orgnr']: xml_data.get('orgnr', ''),
        field_mapping['marked_generell']: xml_data.get('marked_generell', ''),
        field_mapping['bb_poststed']: xml_data.get('bb_poststed', ''),
        field_mapping['bb_adresse1']: xml_data.get('bb_adresse1', ''),
        field_mapping['url']: xml_data.get('url', ''),
        field_mapping['marked_boliglan_info']: xml_data.get('marked_boliglan_info', ''),
        "name": title,
        "slug": slug
    }
    
    # Debug output to verify the payload
    print("Payload for creating Webflow item:")
    for key, value in field_data.items():
        print(f"{key}: {value}")

    response = requests.post(url_base, json={"fieldData": field_data}, headers=headers)
    if response.status_code == 200:
        print(f"Successfully created item for {title} ({orgnr}) in Webflow.")
    else:
        print(f"Failed to create item for {title} ({orgnr}) in Webflow. Status code: {response.status_code}")
        print(f"Error message: {response.json()}")


# Start the script by parsing XML and processing data
parse_xml_and_process()
