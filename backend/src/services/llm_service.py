try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - optional dependency in free-tier envs
    genai = None
    types = None

try:
    from openai import AzureOpenAI
except ImportError:  # pragma: no cover - optional dependency in free-tier envs
    AzureOpenAI = None

from ..config import settings


class LLMService:

    _gemini_client = None
    _azure_client = None

    @classmethod
    def get_gemini_client(cls):

        if genai is None:
            raise ModuleNotFoundError("google-genai package is not installed.")

        if cls._gemini_client is None:

            cls._gemini_client = genai.Client(
                api_key=settings.gemini.google_api_key
            )

        return cls._gemini_client

    @classmethod
    def get_azure_client(cls):

        if AzureOpenAI is None:
            raise ModuleNotFoundError("openai package is not installed.")

        if cls._azure_client is None:

            cls._azure_client = AzureOpenAI(
                api_key=settings.azure_openai.azure_openai_api_key,
                api_version=settings.azure_openai.azure_openai_api_version,
                azure_endpoint=settings.azure_openai.azure_openai_endpoint
            )

        return cls._azure_client

    @classmethod
    def generate(
        cls,
        prompt: str,
        provider: str | None = None
    ) -> str:

        provider = (
            provider
            or settings.llm.provider
            or "azure"
        ).lower()

        if provider == "gemini":

            return cls._generate_gemini(
                prompt
            )

        elif provider == "azure":

            return cls._generate_azure(
                prompt
            )

        raise ValueError(
            f"Unsupported provider: {provider}"
        )

    @classmethod
    def _generate_gemini(
        cls,
        prompt: str
    ) -> str:

        client = cls.get_gemini_client()
        params = settings.llm_params

        config = None
        if types is not None:
            config = types.GenerateContentConfig(
                temperature=params.temperature,
                top_p=params.top_p,
                max_output_tokens=params.max_tokens,
            )

        response = client.models.generate_content(
            model=settings.gemini.gemini_model,
            contents=prompt,
            config=config
        )

        return response.text or ""

    @classmethod
    def _generate_azure(
        cls,
        prompt: str
    ) -> str:

        client = cls.get_azure_client()
        params = settings.llm_params

        response = client.chat.completions.create(
            model=settings.azure_openai.azure_openai_deployment,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=params.temperature,
            top_p=params.top_p,
            max_tokens=params.max_tokens,
            frequency_penalty=params.frequency_penalty,
            presence_penalty=params.presence_penalty
        )

        return response.choices[0].message.content or ""