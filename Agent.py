# SPDX-FileCopyrightText: 2025 German Aerospace Center (DLR)
# SPDX-FileContributor: Tim Rosenbach <tim.rosenbach@dlr.de>
#
# SPDX-License-Identifier: MIT

import base64
import configparser
import time
import requests


config = configparser.ConfigParser()
config.read("config.cfg")
setup = config["setup"]

class Agent:
    """Agent class that can make requests to LLMs.
    Possible models are OpenAI's and Ollama's models.

    Attributes:
    model (str): Model to use for making requests.
    seed (int): Seed to use for generating responses. Default is None.

    Methods:
    make_request(pathToRequest: str, jsonFormat: bool, pathsToImages: list[str] = None) -> str: Makes a request to the model with the given prompt and images. Returns the response.
    """
    model = "none"
    seed = -1

    def __init__(self, model: str, seed: int = None) -> None:
        self.model = model
        self.seed = seed

    def make_request(self, pathToRequest: str, jsonFormat: bool, pathsToImages: list[str] = None) -> str:
        """Makes a request to the model with the given prompt and images. Returns the response.
        
        Args:
            pathToRequest (str): Path to the file containing the prompt.
            jsonFormat (bool): Whether the response should be in JSON format.
            pathsToImages (list[str]): Paths to the images to be used in the request. Default is None.
        
        Returns:
            str: Response from the model.
        """
        request_file = open(pathToRequest, "r")
        prompt = request_file.read()
        request_file.close()

        if self.model.startswith("llama"):
            if pathsToImages is not None and not self.model.endswith("vision"):
                raise Exception("Llama model does not support images.")
            return self._generate_llama_response(prompt, jsonFormat, pathsToImages)
        elif self.model.startswith("gpt"):
            return self._generate_openai_response(prompt, jsonFormat, pathsToImages)
        elif self.model.startswith("llava"):
            return self._generate_llava_response(prompt, jsonFormat, pathsToImages)
            

    def _generate_llama_response(self, prompt: str, jsonFormat: bool, pathsToImages: list[str] = None) -> str:
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 32000,
            }
        }

        if self.seed != None:
            data["options"]["seed"] = self.seed

        if jsonFormat:
            data["format"] = "json"

        if pathsToImages is not None:
            images = []
            for pathToImage in pathsToImages:
                image_base64 = encode_image(pathToImage)
                images.append(image_base64)
            data["images"] = images

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post(setup["ollama_server_ip"] + "/api/generate", json=data, headers=headers)
        response_json = response.json()
        return response_json["response"]


    def _generate_openai_response(self, prompt: str, jsonFormat: bool, pathsToImages: list[str] = None) -> str:
        data = {
            "model": self.model,
            "messages": [
                {
                "role": "user",
                "content": [
                    {
                    "type": "text",
                    "text": prompt
                    }
                ]
                }
            ],
        }

        if self.seed != None:
            data["seed"] = self.seed
        
        if pathsToImages is not None:
            for index, pathToImage in enumerate(pathsToImages):
                image_base64 = encode_image(pathToImage)
                data["messages"][0]["content"].insert(index, 
                    {
                    "type": "image_url",
                    "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                )

        if jsonFormat:
            data["response_format"] = {"type": "json_object"}
            

        headers = {
            'Content-Type': 'application/json',
            'Authorization': "Bearer " + setup["openai_api_key"]
        }
        response = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers)
        response_json = response.json()
        if "error" in response_json:
            print(response_json)
            if response_json["error"]["code"] == "rate_limit_exceeded":
                print("Rate limit exceeded. Waiting for one minute.")
                time.sleep(60)
                return self._generate_openai_response(prompt, jsonFormat, pathsToImages)
            elif response_json["error"]["code"] == "insufficient_quota":
                print("Insufficient quota. Waiting for one minute.")
                time.sleep(60)
                return self._generate_openai_response(prompt, jsonFormat, pathsToImages)
        output = response_json["choices"][0]["message"]["content"]
        return output
    

    def _generate_llava_response(self, prompt: str, jsonFormat: bool, pathsToImages: list[str] = None) -> str:
        images = []
        for pathToImage in pathsToImages:
            image_base64 = encode_image(pathToImage)
            images.append(image_base64)

        data = {
            'model': 'llava:34b',
            'prompt': prompt,
            'images': images,
        }
        
        if self.seed != None:
            if "options" not in data:
                data["options"] = {}
            data["options"]["seed"] = self.seed

        if jsonFormat:
            data["format"] = "json"

        headers = {
            'Content-Type': 'application/json'
        }

        description = ""

        response = requests.post(setup["ollama_server_ip"] + "/api/generate", json=data, headers=headers)
        response_lines = response.text.strip().split("\n")
        for line in response_lines:
            response_json = requests.models.complexjson.loads(line)  # Parse each line as JSON
            description += response_json["response"]
            if response_json["done"]:
                break

        return description
    

def encode_image(image_path: str) -> str:
    """Encodes an image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
  
