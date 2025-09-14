import asyncio
import httpx
import json
import requests
import sys
import threading
import time
import yaml
import base64
import requests
import mimetypes


class Chatbot:
    def __init__(self):
        with open("../config.yaml", "r") as file:
            config = yaml.safe_load(file)

        self.api_key = config["api_key"]
        self.base_url = config["model_server_base_url"]
        self.stream = config["stream"]
        self.stream_timeout = config["stream_timeout"]
        self.workspace_slug = config["workspace_slug"]

        if self.stream:
            self.chat_url = f"{self.base_url}/workspace/{self.workspace_slug}/stream-chat"
        else:
            self.chat_url = f"{self.base_url}/workspace/{self.workspace_slug}/chat"

        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key
        }

    def get_text_content(self, file_path: str) -> str:
        """
        Send a query to llm to parse text content
        """
        try:
            return self.blocking_chat(file_path)
        except Exception as e:
                print("Error! Check the model is correctly loaded. More details in README troubleshooting section.")
                print(e)
                sys.exit(f"Error details: {e}")
                

    def get_base64_encoded_image(self, image_path:str):
        """Encodes an image file to a Base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def get_mime_type(self,image_path:str):
        """Determines the MIME type of an image file."""
        mime_type, _ = mimetypes.guess_type(image_path)
        return mime_type if mime_type else "application/octet-stream"

    def blocking_chat(self, file_path: str) -> str:
        """
        Send a chat request to the model server and return the response
        
        Inputs:
        - message: The message to send to the chatbot
        """

        base64_image = self.get_base64_encoded_image(file_path)
        mime_type = self.get_mime_type(file_path)
        filename = file_path.split("/")[-1]
        print("Reached chatbot")

        data = {
            "message": "Get text from this file",
            "mode": "chat",
            "sessionId": "example-session-id",
            "attachments": [
                 {
                    "name": filename,
                    "mime": mime_type,
                    "contentString": f"data:{mime_type};base64,{base64_image}"
                }
            ]
        }

        print("Sending Request")
        chat_response = requests.post(
            self.chat_url,
            headers=self.headers,
            json=data
        )
        print(chat_response.json())

        try:
            print("Agent: ", end="")
            return chat_response.json()['textResponse']
            
        except ValueError:
            return "Response is not valid JSON"
        except Exception as e:
            return f"Chat request failed. Error: {e}"
        