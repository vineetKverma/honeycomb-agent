from google import genai
from google.genai import types

import config
from gemini_utils import call_with_retry

_client = genai.Client(api_key=config.GEMINI_API_KEY)


def embed_text(text: str) -> list[float]:
    response = call_with_retry(
        _client.models.embed_content,
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768,
        ),
    )
    return response.embeddings[0].values


def embed_concept(concept: dict) -> list[float]:
    return embed_text(f"{concept['name']}. {concept['definition']}")


if __name__ == "__main__":
    vec = embed_text("Backpropagation computes gradients by propagating errors backward through a neural network.")
    print(f"Vector length : {len(vec)}")
    print(f"First 5 values: {vec[:5]}")
