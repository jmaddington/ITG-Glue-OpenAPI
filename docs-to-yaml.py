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
    ]
}

# Helper function to determine parameter type
def get_param_type(validations):
    if 'Must be a number' in validations:
        return 'integer'
    elif 'Must be a String' in validations or 'Must be one of' in validations:
        return 'string'
    elif 'Must be a Hash' in validations:
        return 'object'
    elif 'Must be one of' in validations and ('true' in validations or 'false' in validations):
        return 'boolean'
    else:
        return 'string'

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
    if any(ignore in class_name for ignore in ['page__info', 'sidenav', 'page__apiv1flexible_asset_fields']):
        continue

    # Extract the endpoint details
    h1_tags = div.find_all('h1')
    if h1_tags:
        for h1 in h1_tags:
            endpoint = h1.get_text(strip=True)
            # Match the HTTP method and path
            match = re.match(r'(GET|POST|PUT|DELETE)\s+(\/[^\s]*)', endpoint)
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
                # Initialize the method details
                if method not in openapi_spec['paths'][path]:
                    openapi_spec['paths'][path][method] = {
                        'summary': '',
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
                    params_heading = article.find('h2', string='Params')
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
                                    param_description = desc_cell.get_text(strip=True)
                                    # Determine if the parameter is required
                                    required = 'required' in param_info
                                    # Determine the parameter location
                                    # Check if parameter is already in parameters list
                                    param_in_list = False
                                    for p in parameters:
                                        if p['name'] == param_name:
                                            param_in_list = True
                                            # Update description and schema if needed
                                            p['description'] = param_description
                                            # Determine the parameter type
                                            validations_div = desc_cell.find('div', string=re.compile('Validations:'))
                                            param_type = 'string'
                                            if validations_div:
                                                validations_text = validations_div.find_next('ul').get_text()
                                                param_type = get_param_type(validations_text)
                                            p['schema']['type'] = param_type
                                            break
                                    if not param_in_list:
                                        param_in = 'query'
                                        # Determine the parameter type
                                        validations_div = desc_cell.find('div', string=re.compile('Validations:'))
                                        param_type = 'string'
                                        if validations_div:
                                            validations_text = validations_div.find_next('ul').get_text()
                                            param_type = get_param_type(validations_text)
                                        # Clean up parameter name
                                        param_name_clean = param_name.replace('[', '.').replace(']', '')
                                        param_obj = {
                                            'name': param_name,
                                            'in': param_in,
                                            'description': param_description,
                                            'required': required,
                                            'schema': {
                                                'type': param_type
                                            }
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

# Step 6: Sort the paths and components alphabetically
openapi_spec['paths'] = dict(sorted(openapi_spec['paths'].items()))
if 'schemas' in openapi_spec['components']:
    openapi_spec['components']['schemas'] = dict(sorted(openapi_spec['components']['schemas'].items()))

# Step 7: Convert the OpenAPI specification to YAML format
yaml_output = yaml.dump(openapi_spec, sort_keys=False, allow_unicode=True)

# Step 8: Output the YAML
print(yaml_output)