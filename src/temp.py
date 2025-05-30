# import requests

# query = "yo mama"
# code = requests.get(
#     "http://localhost:5000/generate_code?input=" + query.replace(" ", "%20")
# )


# print(code.content)

import logger as logger
from ai import clean_code, check_syntax

print(clean_code(logger.get_logs()[-1]["data"]["code"]))
