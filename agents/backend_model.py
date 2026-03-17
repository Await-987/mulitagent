import os
from dotenv import load_dotenv
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.models.stub_model import StubTokenCounter
load_dotenv()


def backend_model():
    api_key = os.getenv('OPENAI_API_KEY')
    url = os.getenv('url')

    # return ModelFactory.create(
    #     model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
    #     model_type="qwen3.5-9b",
    #     api_key="sk-qwen35",
    #     url="http://117.186.43.62:4809/v1",
    #     token_counter=StubTokenCounter(),
    #     model_config_dict={
    #         "stream": False
    #     },
    # )

    # return ModelFactory.create(
    #     model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
    #     model_type="qwq32b",
    #     api_key="sk-qwq123",
    #     url="http://117.186.43.62:5032/v1",
    #     token_counter=StubTokenCounter(),
    #     model_config_dict={
    #         "stream": False,
    #     },
    # )

    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type="qwen3.5-plus",
        api_key=api_key,
        url=url
    )


def backend_model_image():
    vl_api_key = os.getenv('QWEN_API_KEY')
    vl_url = os.getenv('url_qwen')

    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type="qwen3.5-9b",
        api_key="sk-qwen35",
        url="http://117.186.43.62:4809/v1",
        token_counter=StubTokenCounter(),
        model_config_dict={
            "stream": False
        },
    )

    # return ModelFactory.create(
    #     model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
    #     model_type="qwen3-vl-plus",
    #     api_key=vl_api_key,
    #     url=vl_url
    # )