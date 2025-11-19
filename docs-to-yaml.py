import requests
from bs4 import BeautifulSoup
import yaml
import re

# Step 1: Fetch the HTML content from the URL
url = 'https://api.itglue.com/developer/'
response = requests.get(url)
html_content = response.text

# Step 2: Parse the HTML content using BeautifulSoup
soup = BeautifulSoup(html_content, 'html.parser')

# Step 2.5: Extract tag descriptions from the documentation
# Find resource introduction divs (those without __index, __show, etc.)
tag_descriptions = {}
all_divs = soup.find_all('div', class_=re.compile('^page__'))
for div in all_divs:
    classes = div.get('class', [])
    first_class = classes[0] if classes else ''

    # Match resource intro pages - they have no __ after the resource name
    # Examples: page__apiv1attachments, page__apiv1configuration_interfaces
    # Not: page__apiv1attachments__index, page__apiv1configurations__show
    if first_class.startswith('page__apiv1'):
        # Extract everything after page__apiv1
        resource_name = first_class.replace('page__apiv1', '')

        # Check if this is an intro page (no __ in resource_name means no operation suffix)
        if '__' not in resource_name:
            # Look for the subtitle div which contains the short description
            subtitle_div = div.find('div', class_='subtitle')
            if subtitle_div:
                description = subtitle_div.get_text(strip=True)

                # Convert resource name to tag name
                # Handle special cases: accounts_user_metrics_daily -> User Metrics, accounts_users -> Users
                if resource_name == 'accounts_user_metrics_daily':
                    tag_name = 'User Metrics'
                elif resource_name == 'accounts_users':
                    tag_name = 'Users'
                else:
                    tag_name = resource_name.replace('_', ' ').title()

                tag_descriptions[resource_name] = {
                    'name': tag_name,
                    'description': description
                }
            else:
                # Fallback to first paragraph if no subtitle found
                article = div.find('article')
                if article:
                    description_p = article.find('p')
                    if description_p:
                        description = description_p.get_text(strip=True)

                        if resource_name == 'accounts_user_metrics_daily':
                            tag_name = 'User Metrics'
                        elif resource_name == 'accounts_users':
                            tag_name = 'Users'
                        else:
                            tag_name = resource_name.replace('_', ' ').title()

                        tag_descriptions[resource_name] = {
                            'name': tag_name,
                            'description': description
                        }

# Step 3: Find all div elements with class starting with 'page__'
divs = soup.find_all('div', class_=re.compile('^page__'))

# Step 4: Initialize the OpenAPI specification dictionary
openapi_spec = {
    'openapi': '3.0.0',
    'info': {
        'title': 'ITGlue API',
        'version': '1.0.0',
        'description': (
            "Generated from https://github.com/jmaddington/ITG-Glue-OpenAPI\n\n"
            "This document strives to accurately represent IT Glue's API in the OpenAPI 3.0 format, but is best effort only. This is NOT\n"
            "an official IT Glue or Kaseya document.\n\n"
            "Find official documentation at https://api.itglue.com/developer/\n"
            "Details of pagination at https://help.itglue.kaseya.com/help/Content/1-admin/it-glue-api/pagination-in-the-it-glue-api.html\n"
            "Details of sorts and filters at https://help.itglue.kaseya.com/help/Content/1-admin/it-glue-api/sorting-and-filtering-in-the-it-glue-api.html\n\n"
            "**Authentication/Request Headers**\n"
            "All API requests require the following headers:\n"
            "- `x-api-key: {{api-token}}`\n"
            "- `Content-Type: application/vnd.api+json`\n\n"
            "Note: If the request does not have a payload, the `Content-Type` header is not required."
        )
    },
    'servers': [
        {
            'url': 'https://api.itglue.com',
            'description': 'Default API server'
        },
        {
            'url': 'https://api.eu.itglue.com',
            'description': 'EU data center'
        },
        {
            'url': 'https://api.au.itglue.com',
            'description': 'Australia data center'
        }
    ],
    'paths': {},
    'components': {
        'schemas': {},
        'securitySchemes': {
            'apiKeyAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'x-api-key'
            }
        }
    },
    'security': [
        {
            'apiKeyAuth': []
        }
    ],
    'tags': []
}

# Track tags we've seen
seen_tags = {}

# Helper function to extract tag from class name and find its description
def extract_tag_from_class(class_name):
    """Extract resource tag from page class name."""
    # Match pattern like 'page__apiv1attachments' or 'page__apiv1configuration_interfaces__index'
    # Need to extract the resource name which can have underscores
    # Pattern: page__apiv1{resource}__ or page__apiv1{resource} (end of string/whitespace)
    match = re.search(r'page__apiv1([a-z_]+?)(?:__|$|\s)', class_name)
    if match:
        resource_name = match.group(1)

        # Look up in tag_descriptions
        if resource_name in tag_descriptions:
            return tag_descriptions[resource_name]['name']

        # Fallback: convert to title case
        tag_name = resource_name.replace('_', ' ').title()
        return tag_name
    return None

# Helper function to add tag if not exists
def ensure_tag(tag_name):
    """Add tag to spec if not already present."""
    if tag_name and tag_name not in seen_tags:
        seen_tags[tag_name] = True

        # Try to find description from extracted tag_descriptions
        description = None
        for resource_name, tag_info in tag_descriptions.items():
            if tag_info['name'] == tag_name:
                description = tag_info['description']
                break

        # Fallback description
        if not description:
            description = f'Operations related to {tag_name.lower()}'

        openapi_spec['tags'].append({
            'name': tag_name,
            'description': description
        })

# Helper function to generate operation summary
def generate_summary(method, path, tag_name):
    """Generate a descriptive summary for the operation."""
    method = method.upper()

    # Extract resource from path
    path_parts = [p for p in path.split('/') if p and not p.startswith('{')]

    # Determine operation type
    if method == 'GET':
        if '{id}' in path or path.endswith('/{id}'):
            return f'Get a specific {tag_name.lower().rstrip("s")} by ID'
        else:
            return f'List all {tag_name.lower()}'
    elif method == 'POST':
        if 'copy' in path:
            return f'Copy {tag_name.lower()}'
        else:
            return f'Create {tag_name.lower()}'
    elif method == 'PATCH':
        if '{id}' in path or path.endswith('/{id}'):
            return f'Update a specific {tag_name.lower().rstrip("s")}'
        else:
            return f'Bulk update {tag_name.lower()}'
    elif method == 'DELETE':
        if '{id}' in path or path.endswith('/{id}'):
            return f'Delete a specific {tag_name.lower().rstrip("s")}'
        else:
            return f'Bulk delete {tag_name.lower()}'

    return ''

# Helper function to determine parameter type
def get_param_type(validations):
    if 'Must be a number' in validations:
        return 'integer'
    elif 'Must be a Boolean' in validations or ('true' in validations.lower() and 'false' in validations.lower()):
        return 'boolean'
    elif 'Must be an Array' in validations:
        return 'array'
    elif 'Must be a Hash' in validations:
        return 'object'
    elif 'Must be a String' in validations or 'Must be one of' in validations:
        return 'string'
    else:
        return 'string'

# Helper function to extract clean description
def clean_description(desc_text):
    """Extract clean description, removing validation and metadata sections."""
    # Split on common markers
    desc_text = desc_text.strip()

    # Remove validations section
    if 'Validations:' in desc_text:
        desc_text = desc_text.split('Validations:')[0]

    # Remove metadata section
    if 'Metadata:' in desc_text:
        desc_text = desc_text.split('Metadata:')[0]

    # Remove notes section that might be inline
    if 'Notes:' in desc_text:
        desc_text = desc_text.split('Notes:')[0]

    return desc_text.strip()

# Helper function to extract validations from the description cell
def extract_validations_from_cell(desc_cell):
    """Extract validation rules from the HTML cell element."""
    validations = []

    # Look for validations strong tag (inside a div)
    validations_strong = desc_cell.find('strong', string=re.compile('Validations:'))
    if validations_strong:
        # The ul should be a sibling or child of the parent div
        parent_div = validations_strong.find_parent('div')
        if parent_div:
            # Try to find the ul - it might be a sibling or after the div
            validations_ul = parent_div.find_next_sibling('ul')
            if not validations_ul:
                validations_ul = parent_div.find('ul')
            if not validations_ul:
                validations_ul = parent_div.find_next('ul')

            if validations_ul:
                for li in validations_ul.find_all('li'):
                    # Get text from li, preserving code elements
                    validation_text = li.get_text(strip=True)
                    validations.append(validation_text)

    return validations

# Helper function to extract enum values from validation text
def extract_enum_values(validation_text):
    """Extract enum values from 'Must be one of:' validation."""
    if 'Must be one of:' in validation_text or 'Must be one of' in validation_text:
        # Split to get the values part
        if 'Must be one of:' in validation_text:
            values_part = validation_text.split('Must be one of:')[1]
        else:
            values_part = validation_text.split('Must be one of')[1]

        # Remove periods and split by comma
        values_part = values_part.strip().rstrip('.')
        # Handle both comma-separated and whitespace-separated values
        enum_values = [v.strip() for v in re.split(r'[,\s]+', values_part) if v.strip()]

        return enum_values if enum_values else None
    return None

# Helper function to check if parameter is a body parameter
def is_body_parameter(param_name, param_info):
    """Determine if a parameter should be in the request body."""
    # Check if it's marked as JSON Body Param
    if 'JSON Body Param' in param_info:
        return True

    # Check if parameter name suggests it's a body param (data, attributes, etc.)
    if param_name.startswith('data[') or param_name.startswith('data'):
        return True

    return False

# Function to check for duplicate parameters
def add_parameter(parameters_list, new_param):
    for param in parameters_list:
        if param['name'] == new_param['name'] and param['in'] == new_param['in']:
            # Duplicate found, do not add
            return
    parameters_list.append(new_param)

# Define endpoints that support filtering and their available filters
available_filters = {
    '/users_metrics': ['date', 'user_ID'],
    '/configurations': ['name', 'status', 'organization_id'],
    '/organizations': ['name', 'status'],
    # Add more endpoints and their filters as needed
}

# Step 5: Iterate over each div and extract the necessary information
for div in divs:
    # Get the class name
    class_names = div.get('class')
    if not class_names:
        continue
    class_name = ' '.join(class_names)

    # Ignore elements as per instructions
    if any(ignore in class_name for ignore in ['page__info', 'sidenav']):
        continue

    # Extract the endpoint details
    h1_tags = div.find_all('h1')
    if h1_tags:
        for h1 in h1_tags:
            endpoint = h1.get_text(strip=True)
            # Match the HTTP method and path
            match = re.match(r'(GET|POST|PATCH|DELETE)\s+(\/[^\s]*)', endpoint)
            if match:
                method = match.group(1).lower()
                path = match.group(2)
                # Replace path parameters with OpenAPI syntax
                path = re.sub(r':(\w+)', r'{\1}', path)
                # Extract path parameters
                path_params = re.findall(r'\{(\w+)\}', path)
                # Initialize the path in the OpenAPI spec if not already present
                if path not in openapi_spec['paths']:
                    openapi_spec['paths'][path] = {}
                # Extract tag from class name
                tag_name = extract_tag_from_class(class_name)

                # Initialize the method details
                if method not in openapi_spec['paths'][path]:
                    # Generate summary
                    summary = generate_summary(method, path, tag_name) if tag_name else ''

                    operation = {
                        'summary': summary,
                        'description': '',
                        'parameters': [],
                        'responses': {
                            '200': {
                                'description': 'Successful response',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object'
                                        }
                                    }
                                }
                            }
                        },
                        'security': [{'apiKeyAuth': []}]
                    }

                    # Add tags if we extracted a valid tag
                    if tag_name:
                        operation['tags'] = [tag_name]
                        ensure_tag(tag_name)

                    openapi_spec['paths'][path][method] = operation
                # Reference to parameters list
                parameters = openapi_spec['paths'][path][method]['parameters']
                # Add path parameters to parameters list
                for param in path_params:
                    param_obj = {
                        'name': param,
                        'in': 'path',
                        'description': '',
                        'required': True,
                        'schema': {
                            'type': 'string'  # Default to string, adjust based on actual type if available
                        }
                    }
                    add_parameter(parameters, param_obj)
                # Add paging, sorting, and filtering parameters for GET methods
                if method == 'get':
                    # Add paging parameters
                    paging_params = [
                        {
                            'name': 'page[size]',
                            'in': 'query',
                            'description': 'Number of items per page (max 1000)',
                            'required': False,
                            'schema': {
                                'type': 'integer',
                                'maximum': 1000
                            }
                        },
                        {
                            'name': 'page[number]',
                            'in': 'query',
                            'description': 'Page number to retrieve',
                            'required': False,
                            'schema': {
                                'type': 'integer',
                                'minimum': 1
                            }
                        }
                    ]
                    for param in paging_params:
                        add_parameter(parameters, param)
                    # Add sorting parameter
                    sort_param = {
                        'name': 'sort',
                        'in': 'query',
                        'description': 'Field by which to sort the results. Prepend \'-\' for descending order.',
                        'required': False,
                        'schema': {
                            'type': 'string'
                        }
                    }
                    add_parameter(parameters, sort_param)
                    # Add filtering parameters based on known filters
                    filters = available_filters.get(path, [])
                    for filter_param in filters:
                        filter_obj = {
                            'name': f'filter[{filter_param}]',
                            'in': 'query',
                            'description': f'Filter results by {filter_param}',
                            'required': False,
                            'schema': {
                                'type': 'string'  # Adjust type as needed
                            }
                        }
                        add_parameter(parameters, filter_obj)
                # Extract description and parameters
                article = div.find('article')
                if article:
                    # Description
                    description = article.find('p')
                    if description:
                        openapi_spec['paths'][path][method]['description'] = description.get_text(strip=True)
                        # Add note about pagination limits
                        if method == 'get':
                            openapi_spec['paths'][path][method]['description'] += (
                                "\n\nNote: The maximum number of results that can be requested is 1000."
                                " If your requests are timing out, try lowering the page size."
                            )
                    # Parameters
                    params_heading = article.find('h2', string=lambda text: text and 'Params' in text)
                    if params_heading:
                        params_table = params_heading.find_next('table')
                        if params_table:
                            rows = params_table.find_all('tr')[1:]  # Skip header
                            for row in rows:
                                cells = row.find_all('td')
                                if len(cells) >= 2:
                                    param_cell = cells[0]
                                    desc_cell = cells[1]
                                    param_name = param_cell.find('strong').get_text(strip=True)
                                    param_info = param_cell.find('small').get_text(strip=True)

                                    # Get clean description from the first <p> tag
                                    desc_p = desc_cell.find('p')
                                    param_description = desc_p.get_text(strip=True) if desc_p else ''

                                    # Extract validations from the HTML structure
                                    validations = extract_validations_from_cell(desc_cell)

                                    # Determine if the parameter is required
                                    required = 'required' in param_info.lower()

                                    # Determine if this is a body parameter
                                    is_body_param = is_body_parameter(param_name, ' '.join(validations) if validations else '')

                                    # Check if parameter is already in parameters list
                                    param_in_list = False
                                    for p in parameters:
                                        if p['name'] == param_name:
                                            param_in_list = True
                                            # Update description and schema if needed
                                            p['description'] = param_description

                                            # Determine the parameter type
                                            param_type = 'string'
                                            if validations:
                                                param_type = get_param_type(' '.join(validations))
                                            p['schema']['type'] = param_type

                                            # Add enum if present
                                            if validations:
                                                for val in validations:
                                                    enum_values = extract_enum_values(val)
                                                    if enum_values and len(enum_values) > 0 and len(enum_values) < 50:
                                                        p['schema']['enum'] = enum_values
                                                        break
                                            break

                                    if not param_in_list:
                                        # Determine parameter location
                                        # Check if param mentions "In URL" or is in path params
                                        validation_text = ' '.join(validations) if validations else ''
                                        if 'In URL' in validation_text or param_name in path_params:
                                            param_in = 'path'
                                        elif method in ['post', 'patch', 'delete'] and is_body_param:
                                            # Skip body parameters for now - they should be in requestBody
                                            continue
                                        else:
                                            param_in = 'query'

                                        # Determine the parameter type
                                        param_type = 'string'
                                        if validations:
                                            param_type = get_param_type(' '.join(validations))

                                        # Build schema
                                        param_schema = {'type': param_type}

                                        # Add enum if "Must be one of" is present
                                        if validations:
                                            for val in validations:
                                                enum_values = extract_enum_values(val)
                                                if enum_values and len(enum_values) > 0 and len(enum_values) < 50:
                                                    param_schema['enum'] = enum_values
                                                    break

                                        param_obj = {
                                            'name': param_name,
                                            'in': param_in,
                                            'description': param_description,
                                            'required': required,
                                            'schema': param_schema
                                        }
                                        add_parameter(parameters, param_obj)
                    # Responses
                    errors_heading = article.find('h2', string='Errors')
                    if errors_heading:
                        responses_table = errors_heading.find_next('table')
                        if responses_table:
                            rows = responses_table.find_all('tr')[1:]  # Skip header
                            for row in rows:
                                cells = row.find_all('td')
                                if len(cells) >= 2:
                                    code = cells[0].get_text(strip=True)
                                    description = cells[1].get_text(strip=True)
                                    openapi_spec['paths'][path][method]['responses'][code] = {
                                        'description': description
                                    }

# Step 6: Sort the paths, tags, and components alphabetically
openapi_spec['paths'] = dict(sorted(openapi_spec['paths'].items()))
openapi_spec['tags'] = sorted(openapi_spec['tags'], key=lambda x: x['name'])
if 'schemas' in openapi_spec['components']:
    openapi_spec['components']['schemas'] = dict(sorted(openapi_spec['components']['schemas'].items()))

# Step 7: Convert the OpenAPI specification to YAML format
yaml_output = yaml.dump(openapi_spec, sort_keys=False, allow_unicode=True)

# Step 8: Output the YAML
print(yaml_output)
