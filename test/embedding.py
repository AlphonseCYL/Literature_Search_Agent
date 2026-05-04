import dashscope
from openai import OpenAI
from http import HTTPStatus
from dotenv import load_dotenv
import os

load_dotenv()  # 加载环境变量
input_text = "衣服的质量杠杠的"

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),  
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

completion = client.embeddings.create(
    model="text-embedding-v4",
    input=input_text
)

print(completion.model_dump_json())