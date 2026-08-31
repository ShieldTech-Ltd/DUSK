from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelProfile:
    name: str
    slug: str
    model_id: str
    provider: str = "mantle"


MODEL_PROFILES = (
    ModelProfile("Kimi K2.5", "kimi-k2-5", "moonshotai.kimi-k2.5"),
    ModelProfile("GLM-5", "glm-5", "zai.glm-5"),
    ModelProfile("Qwen3 32B", "qwen3-32b", "qwen.qwen3-32b"),
    ModelProfile("GPT OSS 120B", "gpt-oss-120b", "openai.gpt-oss-120b"),
)


def get_model_profile(model_id: str) -> ModelProfile:
    for profile in MODEL_PROFILES:
        if profile.model_id == model_id:
            return profile
    raise ValueError(f"Unsupported Bedrock Mantle model: {model_id}")
