import os
from aws_bedrock_token_generator import provide_token
from openai import OpenAI

REGION = "us-east-2"
token = provide_token(region=REGION)

os.environ['OPENAI_API_KEY'] = token
os.environ['OPENAI_BASE_URL'] = f'https://bedrock-mantle.{REGION}.api.aws/openai/v1'

def main():
    client = OpenAI()

    response = client.responses.create(
        model="openai.gpt-5.5",
        input=[
            {"role": "user", "content": "Hello!"}
        ]
    )

    print(f"{response.output_text=}")

if __name__ == "__main__":
    main()
