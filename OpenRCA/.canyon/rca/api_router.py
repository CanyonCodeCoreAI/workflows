import json
import os
import time
from typing import Any, Dict, Optional

_DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
_MODEL_KEY = "gemini3pro"

def _load_config() -> Dict[str, Any]:
    config_path = os.environ.get("API_CONFIG_PATH") or _DEFAULT_CONFIG_PATH
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(__file__), "..", config_path)
    
    # CanyonOS: config.json holds an API key, so it is not shipped in the image.
    # Without it, the model comes from OPENRCA_MODEL and the key from OPENAI_API_KEY.
    meta_config = {}
    if os.path.isfile(config_path):
        with open(config_path, "r") as f:
            meta_config = json.load(f)
    
    model_config = meta_config.get(_MODEL_KEY, {})
    
    return {
        "MODEL": model_config.get("model", os.environ.get("OPENRCA_MODEL", _MODEL_KEY)),
        "API_KEY": model_config.get("api_key"),
        "API_BASE": model_config.get("base_url"),
        "TEMPERATURE": model_config.get("temperature", 0.0),
    }

configs = _load_config()

def get_chat_completion(messages, temperature: Optional[float] = None, tools=None, parallel_tool_calls: bool = False):
    from openai import OpenAI

    if temperature is None:
        temperature = configs["TEMPERATURE"]

    client_args = {"api_key": configs["API_KEY"]}
    # CanyonOS: OPENAI_BASE_URL points at the in-container LLM gateway; the
    # configured base_url is the upstream (set OPENAI_UPSTREAM_BASE for it there).
    base_url = os.environ.get("OPENAI_BASE_URL") or configs["API_BASE"]
    if base_url:
        client_args["base_url"] = base_url
    client = OpenAI(**client_args)

    request_args: Dict[str, Any] = {
        "model": configs["MODEL"],
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        request_args["tools"] = tools
        request_args["parallel_tool_calls"] = parallel_tool_calls

    for _ in range(3):
        try:
            return client.chat.completions.create(**request_args).choices[0].message.content
        except Exception as e:
            print(e)
            if "429" in str(e):
                print("Rate limit exceeded. Waiting for 1 second.")
                time.sleep(1)
                continue
            raise e

if __name__ == "__main__":
    print(f"Model: {configs['MODEL']}")
    response = get_chat_completion([{"role": "user", "content": "123+321=?"}])
    print(response)