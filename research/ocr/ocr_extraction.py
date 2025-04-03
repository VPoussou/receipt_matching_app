import base64
import dotenv
from langchain.prompts import HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List
from langchain_mistralai.chat_models import ChatMistralAI
from datetime import date
import os
import cv2

async def ocr_extraction(image_path):
    dotenv.load_dotenv()
    MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]

    # 1. Define Pydantic Output Model
    class ExtractedData(BaseModel):
        """Represents extracted data from a document."""

        date_of_purchase: date | str = Field(description="The date found in the document (YYYY-MM-DD). If not date is found return an empty string")
        name_of_store: str = Field(description="The name of the vendor or store in the document")
        address: str = Field(description="The full address found in the document.")
        total_price: float = Field(description="The total price found in the document.")
        currency: str | None = Field(description="The currency of the total price (e.g., USD, EUR, GBP) Do not make it up if not present.")

    # 2. Image to Base64 Encoding (if needed) - Moved here for clarity
    async def encode_and_preprocess_image_to_base64(image_path):
        """Encodes an image from a file path to a base64 string."""
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        try:
                _, buffer = cv2.imencode('.jpg', thresh)
                return base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            print(f"Error encoding image to base64: {e}")
            return None


    # 3. Langchain Setup with ChatMistralAI
    chat_mistral = ChatMistralAI(mistral_api_key=MISTRAL_API_KEY, model_name="pixtral-12b") 

    #TODO Enlever les prompts du code
    # 4. Prompt Template - Improved Prompt
    PROMPT = """
                Please retrieve the named entities requested from the image provided, do not make up anything, if the information is not present return an empty string. Do not infer currency if it is not written explicitely.
                Desired structure : {structure}
            """

    # 5. Output Parser
    parser = PydanticOutputParser(pydantic_object=ExtractedData)

    message = HumanMessagePromptTemplate.from_template(template=PROMPT)
    encoded_image_url = f'data:image/jpeg;base64,{await encode_and_preprocess_image_to_base64(image_path)}'
    role_message = {
        "role":"system",
        "content": [
            {"type":"text",
            "text":"You are an accountant that describes images without making anything up"
        }]
    }
    image_message = {
        "role":"user",
        "content": [
        {
            "type": "image_url",
            "image_url": "{image}"
        }]
    }
    chat_prompt = ChatPromptTemplate.from_messages(messages=[role_message, message, image_message])
    chat_prompt_with_values = chat_prompt.format_prompt(image=encoded_image_url, structure=parser.get_format_instructions())

    response = chat_mistral.invoke(chat_prompt_with_values.to_messages())
    data = parser.parse(response.content)
    

    return(data )
