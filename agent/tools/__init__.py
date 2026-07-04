"""Tool registry.

Two things the loop needs:
  TOOLS    name -> the Python function to run
  SCHEMAS  the list of JSON schemas we hand to the model

Registering a new tool is a one-line change in each collection below. The loop
never hard-codes tool names; it looks everything up here.
"""

from .calculator import calculator, SCHEMA as CALCULATOR_SCHEMA
from .convert import convert, SCHEMA as CONVERT_SCHEMA
from .current_datetime import current_datetime, SCHEMA as CURRENT_DATETIME_SCHEMA
from .fetch_url import fetch_url, SCHEMA as FETCH_URL_SCHEMA
from .web_search import web_search, SCHEMA as WEB_SEARCH_SCHEMA

TOOLS = {
    "calculator": calculator,
    "convert": convert,
    "current_datetime": current_datetime,
    "fetch_url": fetch_url,
    "web_search": web_search,
}

SCHEMAS = [
    CALCULATOR_SCHEMA,
    CONVERT_SCHEMA,
    CURRENT_DATETIME_SCHEMA,
    FETCH_URL_SCHEMA,
    WEB_SEARCH_SCHEMA,
]
