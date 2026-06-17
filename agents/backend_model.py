import os
from dotenv import load_dotenv
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.models.stub_model import StubTokenCounter
load_dotenv()

QWEN_MODEL_TYPE = os.environ.get("AIOS_MODEL_TYPE", "qwen3.6-27b")
QWEN_BASE_URL = os.environ.get("url") or os.environ.get("OPENAI_BASE_URL") or "http://117.186.43.62:5027/v1"
QWEN_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("QWEN_API_KEY") or ""


def backend_model():
    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type=QWEN_MODEL_TYPE,
        api_key=QWEN_API_KEY,
        url=QWEN_BASE_URL,
        token_counter=StubTokenCounter(),
        model_config_dict={
            "stream": False,
            "max_tokens": int(os.environ.get("AIOS_MODEL_MAX_TOKENS", "4096")),
        },
    )


def backend_model_image():
    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type=QWEN_MODEL_TYPE,
        api_key=QWEN_API_KEY,
        url=QWEN_BASE_URL,
        token_counter=StubTokenCounter(),
        model_config_dict={
            "stream": False,
            "max_tokens": int(os.environ.get("AIOS_VISION_MODEL_MAX_TOKENS", "2048")),
        },
    )
