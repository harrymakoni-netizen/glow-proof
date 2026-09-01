"""Turn skin-analysis scores into a plain-language consultation and routine.

This closes the gap Perfect Corp itself names as the industry weakness: a
score of 58 for pores tells a shopper nothing about what to do on Tuesday
morning.

The model decides WHAT is needed - a product type and the active ingredient
that addresses the measured concern. It deliberately does NOT name brands.
products.py then finds WHICH real product satisfies that, live. Keeping those
two jobs apart is what makes the recommendation unbiased and stops the model
inventing products that do not exist.

Two providers are supported. Anthropic wins when both keys are present;
otherwise whichever key exists; otherwise the canned fallback. The prompt and
the Routine schema are shared, so swapping providers changes nothing the user
can see.

Claims discipline is enforced in the system prompt. This is cosmetic guidance,
not a diagnosis, and a panel drawn from privacy- and compliance-heavy
companies will notice the difference.
"""
import json
import time
from typing import List

from pydantic import BaseModel, Field

from . import config


class Priority(BaseModel):
    concern_key: str = Field(description="One of the concern keys supplied in the input")
    headline: str = Field(description="Plain-language name of what was measured, max 6 words")
    what_it_means: str = Field(description="One or two sentences. No jargon, no diagnosis.")


class Step(BaseModel):
    order: int
    action: str = Field(description="What to do, e.g. 'Cleanse', 'Treat', 'Protect'")
    product_type: str = Field(
        default="",
        description="Generic product category to buy, e.g. 'niacinamide serum', "
                    "'mineral sunscreen SPF 50'. NEVER a brand name. Empty "
                    "string if the step needs no product.")
    key_ingredient: str = Field(
        default="",
        description="The active ingredient that does the work, e.g. 'niacinamide'. "
                    "Empty string if not applicable.")
    note: str = Field(description="One short sentence on how or why")


class RedLightProtocol(BaseModel):
    applicable: bool = Field(description="False if red light is not a sensible fit here")
    wavelength_nm: str = Field(description="e.g. '633nm + 830nm', or '' if not applicable")
    minutes_per_session: int
    sessions_per_week: int
    guidance: str = Field(description="How to run it safely and what to pair it with")


class Routine(BaseModel):
    greeting: str = Field(description="Two warm sentences addressed to the user. No hype, no fear.")
    priorities: List[Priority] = Field(description="Exactly the concerns supplied as priorities")
    am: List[Step]
    pm: List[Step]
    red_light: RedLightProtocol
    what_to_expect: str = Field(description="Realistic 4-8 week expectation, hedged appropriately")


SYSTEM = """You are a skincare advisor interpreting objective AI skin-analysis \
measurements for a consumer.

Translate numeric scores into something a person can act on tomorrow morning.

Rules you must follow:
- Scores run 0-100 where HIGHER IS BETTER. A low score means that concern \
needs attention.
- NEVER name a brand or a specific product. Name the product TYPE and the \
ACTIVE INGREDIENT only. A separate system finds real products afterwards, \
and inventing brand names would make it recommend things that do not exist.
- This is cosmetic guidance, never a medical diagnosis. Do not name diseases, \
do not claim to treat or cure anything, and do not promise results. Hedge \
efficacy language ("studies suggest", "many people see") rather than \
asserting it.
- If results suggest something a professional should look at, say so plainly \
and briefly, without alarm.
- Always include sun protection in the morning routine when any active is \
recommended.
- Keep routines short: three to four steps each. A routine nobody follows \
helps nobody.
- Warm, direct, specific. No filler, no marketing voice, no exclamation marks."""


def _fallback(analysis) -> Routine:
    """Canned routine for when no LLM key is set, or the live call fails.

    Deliberately competent rather than obviously broken - the whole flow can
    be demoed offline, and it degrades to something honest if the live call
    dies on stage. It is NOT personalised: two very different faces get very
    similar answers, which is exactly why a real provider matters.
    """
    top = analysis.priorities
    worst = top[0].key if top else "texture"
    treat = {
        "pore": ("niacinamide serum", "niacinamide"),
        "acne": ("salicylic acid treatment", "salicylic acid"),
        "wrinkle": ("retinal night serum", "retinal"),
        "texture": ("gentle exfoliating serum", "lactic acid"),
        "redness": ("azelaic acid serum", "azelaic acid"),
        "age_spot": ("vitamin C serum", "vitamin C"),
        "oiliness": ("niacinamide serum", "niacinamide"),
        "moisture": ("hyaluronic acid serum", "hyaluronic acid"),
        "dark_circle": ("caffeine eye serum", "caffeine"),
        "radiance": ("vitamin C serum", "vitamin C"),
    }.get(worst, ("niacinamide serum", "niacinamide"))

    return Routine(
        greeting=("Here is what the scan picked up, in plain terms. "
                  "Nothing here is alarming - it is a starting baseline."),
        priorities=[Priority(concern_key=c.key, headline=c.label,
                             what_it_means=f"{c.blurb}. Measured at {c.ui_score}/100.")
                    for c in top],
        am=[
            Step(order=1, action="Cleanse", product_type="gentle gel cleanser",
                 key_ingredient="", note="Lukewarm water, no scrubbing."),
            Step(order=2, action="Moisturise", product_type="ceramide moisturiser",
                 key_ingredient="ceramides", note="On slightly damp skin."),
            Step(order=3, action="Protect", product_type="mineral sunscreen SPF 50",
                 key_ingredient="zinc oxide",
                 note="Every morning, regardless of weather."),
        ],
        pm=[
            Step(order=1, action="Cleanse", product_type="gentle gel cleanser",
                 key_ingredient="", note="Removes the day before actives go on."),
            Step(order=2, action="Treat", product_type=treat[0],
                 key_ingredient=treat[1],
                 note="Start twice a week and build up slowly."),
            Step(order=3, action="Moisturise", product_type="ceramide moisturiser",
                 key_ingredient="ceramides", note="Seals everything in."),
        ],
        red_light=RedLightProtocol(
            applicable=True, wavelength_nm="633nm + 830nm",
            minutes_per_session=10, sessions_per_week=4,
            guidance=("Clean, dry skin before a session. Eyes closed. "
                      "Consistency matters more than session length."),
        ),
        what_to_expect=("Most people need six to eight weeks of consistency "
                        "before a re-scan shows movement. Re-scan monthly "
                        "against this baseline rather than judging day to day."),
    )


def _payload(analysis) -> dict:
    return {
        "measurements": [
            {"key": c.key, "label": c.label, "score_0_100": c.ui_score,
             "meaning": c.blurb}
            for c in analysis.concerns
        ],
        "priorities": [c.key for c in analysis.priorities],
    }


def _prompt(analysis) -> str:
    return "Skin analysis results:\n" + json.dumps(_payload(analysis), indent=2)


def _via_anthropic(analysis) -> Routine:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_KEY)
    response = client.messages.parse(
        model=config.ANTHROPIC_MODEL,
        max_tokens=16000,
        system=SYSTEM,
        # Medium effort: this is a formatting-and-tone task, not a reasoning
        # problem, and every second here is dead air in the demo.
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": _prompt(analysis)}],
        output_format=Routine,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    return response.parsed_output


def _via_gemini(analysis) -> Routine:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_KEY)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=_prompt(analysis),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
            response_schema=Routine,
        ),
    )
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, Routine):
        return parsed
    # Some SDK builds return text only. Validate rather than trust the shape.
    return Routine.model_validate_json(response.text)


# Free tiers throttle and occasionally 503 under load. Observed on Gemini
# free tier: a call succeeds, the next two return
# "This model is currently experiencing high demand". Retrying clears it, and
# a demo should not fall back to canned text over a two-second blip.
_TRANSIENT = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED",
              "overloaded", "high demand", "timeout", "Timeout")


def _is_transient(e: Exception) -> bool:
    s = str(e)
    return any(m in s for m in _TRANSIENT)


def generate(analysis, attempts: int = 3) -> dict:
    """Produce a routine via whichever provider is configured.

    Retries transient upstream failures, then degrades to the canned routine
    rather than breaking the screen - a demo must never die on a third-party
    hiccup, but it also should not give up on the first one.
    """
    if not config.LIVE_LLM:
        return {"routine": _fallback(analysis).model_dump(), "live": False}

    fn = _via_anthropic if config.LLM_PROVIDER == "anthropic" else _via_gemini
    last = None
    for i in range(attempts):
        try:
            return {"routine": fn(analysis).model_dump(), "live": True,
                    "provider": config.LLM_PROVIDER, "attempts": i + 1}
        except Exception as e:  # noqa: BLE001 - never let the demo die here
            last = e
            if i + 1 < attempts and _is_transient(e):
                time.sleep(1.5 * (i + 1))
                continue
            break

    return {"routine": _fallback(analysis).model_dump(), "live": False,
            "provider": config.LLM_PROVIDER, "error": str(last)}
