from datetime import datetime
import os
from openai import OpenAI
import logger
from dotenv import load_dotenv

load_dotenv()
model_config = {
    "moneyhog": {
        "model": "google/gemini-2.5-pro-preview",
        "client": OpenAI(base_url="https://openrouter.ai/api/v1"),
        "key": "OPENROUTER_API_KEY",
    },
    "openai": {
        "model": "gpt-4.1-2025-04-14",
        "client": OpenAI(),
        "key": "OPENAI_API_KEY",
    },
}


class AI:
    def __init__(self):
        self.system_prompt = self.get_system_prompt()
        self.config = model_config["openai"]
        self.model = self.config["model"]
        self.client = self.config["client"]
        self.client.api_key = os.getenv(self.config["key"])
        # self.model = "gpt-4.1-2025-04-14"
        # self.model = "gpt-4.1-mini-2025-04-14"

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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": query},
                ],
                max_tokens=3000,
            )
            print(response)
            generated_code = response.choices[0].message.content
            return generated_code
        except Exception as e:
            return e


if __name__ == "__main__":
    ai = AI()
    print(ai.generate_code("select all rooms in the current view"))
