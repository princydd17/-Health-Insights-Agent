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

stop_loading = False

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

    def get_text_content(self, file_path,document_type) -> str:
        """
        Send a query to llm to parse text content
        """
        try:
            print("Making a call")
            return self.blocking_chat(file_path,document_type)
        except Exception as e:
                print("Error! Check the model is correctly loaded. More details in README troubleshooting section.")
                print(e)
                sys.exit(f"Error details: {e}")

    def get_summary_content(self, prompt) -> str:
        """
        Send a query to llm to parse text content
        """
        try:
            print("Making a call")
            return self.blocking_summary_chat(prompt)
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

    def loading_indicator(self) -> None:
        """
        Display a loading indicator in the console while the chat request is being processed
        """
        while not stop_loading:
            continue
        print('')
    def blocking_chat(self, file_path: str, document_type: str) -> str:
        """
        Send a chat request to the model server and return the response
        
        Inputs:
        - message: The message to send to the chatbot
        """

        global stop_loading
        stop_loading = False
        loading_thread = threading.Thread(target=self.loading_indicator)
        loading_thread.start()
        base64_image = self.get_base64_encoded_image(file_path)
        mime_type = self.get_mime_type(file_path)
        filename = file_path.split("/")[-1]
        print("Reached chatbot")
        prompt = """Extract laboratory report information from the given text image as accurately as possible. Provide the output as a list of JSON objects, with each object representing one reported test.

        Each JSON object must include the following fields (if available):

        test_name

        test_code (if present)

        result_value

        result_unit

        reference_range

        interpretation (e.g., Normal, High, Low, Abnormal)

        test_date

        ordering_doctor

        notes (any additional remarks provided in the report)

        If a field is missing in the report, set its value to null instead of omitting it. The final output should always be a list, even if there is only one test."""
        
        if document_type!="lab_report":
            prompt = """Extract prescription information from the given text image as accurately as possible. Provide the output as a list of JSON objects, with each object representing one prescribed medicine.

            Each JSON object must include the following fields (if available):

            medication_name

            dosage

            frequency (e.g., once daily, twice daily)

            time_of_day (e.g., morning, evening, before food, after food)

            start_date

            end_date

            prescribing_doctor

            notes (any additional instructions like ‘take with water’)

            If a field is missing in the prescription, set its value to null instead of omitting it. The final output should always be a list, even if there is only one medication."""

        data = {
            "message": prompt,
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
        print(document_type)
        print(prompt)
        print("Sending Request")
        chat_response = requests.post(
            self.chat_url,
            headers=self.headers,
            json=data
        )
        stop_loading = True
        loading_thread.join()
        buffer = chat_response.text
        print(buffer)
        parsedText = ""
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if line.startswith("data: "):
                line = line[len("data: "):]
            try:
                parsed_chunk = json.loads(line.strip())
                # print(parsed_chunk.get("textResponse", ""), end="", flush=True)
                parsedText+= parsed_chunk.get("textResponse", "")
                if parsed_chunk.get("close", False):
                    parsedText+= ""
            except json.JSONDecodeError:
                # The line is not a complete JSON; wait for more data.
                continue
            except Exception as e:
                # generic error handling, quit for debug
                print(f"Error processing chunk: {e}")
        try:
            return parsedText
            
        except ValueError:
            return "Response is not valid JSON"
        except Exception as e:
            return f"Chat request failed. Error: {e}"
        
    def blocking_summary_chat(self, prompt) -> str:
        """
        Send a chat request to the model server and return the response
        
        Inputs:
        - message: The message to send to the chatbot
        """

        global stop_loading
        stop_loading = False
        loading_thread = threading.Thread(target=self.loading_indicator)
        loading_thread.start()
        
        print("Reached chatbot")
        
        data = {
            "message": prompt,
            "mode": "chat",
            "sessionId": "example-session-id",
            "attachments": []
        }
        
        print("Sending Request")
        chat_response = requests.post(
            self.chat_url,
            headers=self.headers,
            json=data
        )
        stop_loading = True
        loading_thread.join()
        buffer = chat_response.text
        print(buffer)
        parsedText = ""
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if line.startswith("data: "):
                line = line[len("data: "):]
            try:
                parsed_chunk = json.loads(line.strip())
                # print(parsed_chunk.get("textResponse", ""), end="", flush=True)
                parsedText+= parsed_chunk.get("textResponse", "")
                if parsed_chunk.get("close", False):
                    parsedText+= ""
            except json.JSONDecodeError:
                # The line is not a complete JSON; wait for more data.
                continue
            except Exception as e:
                # generic error handling, quit for debug
                print(f"Error processing chunk: {e}")
        try:
            return parsedText
            
        except ValueError:
            return "Response is not valid JSON"
        except Exception as e:
            return f"Chat request failed. Error: {e}"
            