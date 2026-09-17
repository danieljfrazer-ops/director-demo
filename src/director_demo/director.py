from __future__ import annotations

import json
from typing import Final, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.shared_params import ResponseFormatJSONSchema

from director_demo.config import Settings
from director_demo.schemas import ShotPlan

SYSTEM_PROMPT: Final[str] = """\
You are the planning engine for a film-director application. Convert the user's
source material into a production-ready shot plan that exactly matches the
provided schema.

Editorial rules:
- Preserve the story, tone, dialogue, and causal sequence. Do not invent plot.
- Prefer shots of about 5 seconds. Use 1-10 seconds only when the action demands it.
- Every shot has one clear dramatic purpose and one legible camera idea.
- Keep screen direction, eyelines, time of day, props, injuries, dirt, wardrobe,
  spatial relationships, and character knowledge continuous between shots.
- Create stable IDs for characters and locations, and use them consistently.
- Seeds must be deterministic-looking non-negative integers and should differ per shot.

Prompt rules:
- image_prompt describes a single static starting frame. Establish identity,
  physical traits, clothing, environment, lighting, lens/composition, and style.
- motion_prompt contains 4-8 flowing present-tense sentences. It describes only
  changes over time: subject action, facial/body motion, camera movement, timing,
  dialogue delivery, ambience, music, and sound effects.
- For image-to-video, motion_prompt MUST NOT re-describe stable appearance,
  wardrobe, scenery, lighting, or composition. Refer to characters by name/ID and
  describe what moves or changes. This avoids fighting the conditioning image.
- Do not use keyword soup in motion_prompt. Make movement physically plausible.
- Put exact spoken words in audio.dialogue. Do not silently rewrite dialogue.
- Write continuity_in/out as explicit, testable state facts.

Planning rules:
- Treat references as authoritative. Do not infer rights or identity from them.
- Break action at natural edit points. Avoid generating an entire scene as one clip.
- For the M5/32 GB local profile, every shot must be 1-5 seconds. Split longer
  dramatic beats at a motivated edit point; never request a shot longer than 5 seconds.
- Prefer motivated cuts. State the outgoing transition; default to a hard cut.
- If source details are missing, choose the least surprising cinematic option and
  keep that choice consistent throughout the plan.
"""


class DirectorError(RuntimeError):
    """Raised when the planning model cannot produce a valid shot plan."""


def create_shot_plan(script: str, settings: Settings | None = None) -> ShotPlan:
    """Convert raw source material into a validated, structured shot plan.

    The default uses OpenAI Structured Outputs. Setting provider to ``compatible``
    routes through an OpenAI-compatible local endpoint and validates its JSON locally.
    """
    if not script.strip():
        raise ValueError("script must not be empty")

    config = settings or Settings()
    api_key = config.openai_api_key or config.director_llm_api_key
    if not api_key:
        raise DirectorError("No LLM API key configured")

    client = OpenAI(api_key=api_key, base_url=config.director_llm_base_url)
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": script},
    ]

    if config.director_llm_provider == "openai":
        completion = client.chat.completions.parse(
            model=config.director_llm_model,
            messages=messages,
            response_format=ShotPlan,
        )
        message = completion.choices[0].message
        if message.refusal:
            raise DirectorError(f"Planning request refused: {message.refusal}")
        if message.parsed is None:
            raise DirectorError("Planning model returned no structured shot plan")
        return message.parsed

    if config.director_llm_provider == "compatible":
        json_response_format: ResponseFormatJSONSchema = {
            "type": "json_schema",
            "json_schema": {
                "name": "director_shot_plan",
                "description": "A production-ready, continuity-aware film shot plan.",
                "schema": cast(dict[str, object], ShotPlan.model_json_schema()),
                "strict": True,
            },
        }
        local_completion = client.chat.completions.create(
            model=config.director_llm_model,
            messages=messages,
            response_format=json_response_format,
            temperature=0,
        )
        content = local_completion.choices[0].message.content
        if not content:
            raise DirectorError("Local planning model returned no JSON")
        return ShotPlan.model_validate(json.loads(content))

    raise DirectorError(f"Unsupported LLM provider: {config.director_llm_provider}")
