from datetime import datetime
import os
import openai
import logger
from dotenv import load_dotenv

load_dotenv()


class AI:
    def __init__(self):
        self.system_prompt = self.get_system_prompt()
        self.model = "gpt-4.1-2025-04-14"
        # self.model = "gpt-4.1-mini-2025-04-14"
        openai.api_key = os.getenv("OPENAI_API_KEY")

    def get_system_prompt(self):
        try:
            system_file_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "system.txt"
            )
            with open(system_file_path, "r") as f:
                return f.read().strip()
        except Exception as e:
            raise e

    def generate_code(self, query):
        try:
            # Update the system prompt then get the response
            self.system_prompt = self.get_system_prompt()
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": query},
                ],
            )
            generated_code = response.choices[0].message.content
            return generated_code
        except Exception as e:
            return e


# if __name__ == "__main__":
