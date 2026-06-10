"""
Opus assessment runner — calls the configurable model with the evidence package.

Sonnet builds the package. Opus judges.
Model is configurable via config.py — do not hardcode model names here.

Khmer is generated in a SEPARATE second call after English is approved.
Auto-send of Khmer is BLOCKED until khmer_validator passes.
"""

import json
import logging
import jsonschema
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)

# ── Config defaults (override in config.py) ────────────────────────────────────
ASSESSMENT_MODEL          = getattr(config, "ASSESSMENT_MODEL",   "claude-opus-4-8")
ASSESSMENT_PROVIDER       = getattr(config, "ASSESSMENT_PROVIDER", "anthropic")
ASSESSMENT_PROMPT_VERSION = getattr(config, "ASSESSMENT_PROMPT_VERSION", "hiring_applicant_v1")
RUBRIC_VERSION            = getattr(config, "RUBRIC_VERSION", "twb_2026_v1")


# ── Opus system prompt ─────────────────────────────────────────────────────────
_ASSESSMENT_SYSTEM = """\
You are the hiring assessment brain for The Wine Bakery (Cambodia).
You receive a structured evidence package from the intake funnel and quiz.
Your job is to produce a hiring judgment, NOT a school grade.

SCORING PHILOSOPHY — READ CAREFULLY:
- Mechanical percentage is supporting context, not the hiring decision.
- A 80% score with critical hiding-mistake answers + blame-shifting = risky.
- A 62% score with honest "I don't know" answers + clean process = possibly better trial.
- Critical signals can override a high percentage.
- Your job is to identify which answers REVEAL the person, not count correct answers.

CRITICAL SIGNALS (any one of these can cap the recommendation):
- Hides mistakes from supervisor
- Lies or changes story for convenience
- Protects lazy/bad coworker behavior
- Refuses cross-help or team responsibility
- Blames customer or colleagues automatically
- Cannot or will not accept correction
- Ignores instructions repeatedly
- Thinks prior experience means not following our way
- Gives seriously incomplete answers to multi-part questions
- Resists targeted correction

CANDIDATE TYPES:
- applicant_hiring_screen: judge by entry-level or experience-adjusted expectations
- leadership_audit: judge by senior/chef-level expectations, NOT entry-level
- retraining_review: focus on gap and trainability

OUR PAY RULES (for offer suggestions):
- 9h/day:  $160 base + $15 bonus + 4,500 riel food/day
- 10h/day: $170 base + ~$15 bonus + 5,000 riel food/day
- 11h/day: $190 base + ~$20 bonus + 5,500 riel food/day
- 12h/day: $210 base + $20 bonus + 6,000 riel food/day
- Experienced applicants with useful experience but red flags: $180-$200 base (9h)
- Do NOT anchor to applicant's claimed previous salary
- Exact CV dates matter; vague dates are weaker; short-job pattern is a red flag
- Experience can be useful or contaminated by bad workplace culture

EVIDENCE RULE: Every finding MUST cite evidence_refs (question IDs, intake flags, or Part E IDs).
Do NOT make unsupported claims. Opus judges patterns from raw evidence.

OUTPUT: Return ONLY valid JSON. No prose. No markdown.
"""

_ASSESSMENT_USER_TEMPLATE = """\
Here is the evidence package. Assess this candidate.

{package_json}

Return ONLY valid JSON matching this schema (no markdown, no extra text):
{{
  "assessment_version": "v1",
  "model": "{model}",
  "prompt_version": "{prompt_version}",
  "rubric_version": "{rubric_version}",
  "overall_recommendation": "hire|trial|hold_for_retest|reject|reject_unless_owner_override|hold_clarify_first",
  "confidence": 0.0-1.0,
  "confidence_by_section": {{"intake": 0.0, "quiz_objective": 0.0, "quiz_written": 0.0, "honesty_check": 0.0, "parte_practical": 0.0}},
  "score_vs_judgment_note": "explain why percentage may be misleading or not",
  "recommendation_cap": null_or_string,
  "cap_reason": null_or_string,
  "critical_signal_hits": [
    {{"signal": "...", "severity": "critical|serious|moderate", "evidence_refs": [...], "raw_quote": "...", "interpretation": "...", "source": "rule|semantic"}}
  ],
  "evidence_based_findings": [
    {{"finding_type": "strength|risk|critical|moderate|partial|positive", "description": "...", "evidence_refs": [...], "raw_quote": "...", "confidence": 0.0}}
  ],
  "who_is_this_person": "2-3 sentences for the owner",
  "likely_work_style": "...",
  "strengths": ["...", "..."],
  "risks": ["...", "..."],
  "red_flags": [],
  "honesty_risk": "low|low_medium|medium|medium_high|high",
  "reliability_risk": "low|low_medium|medium|medium_high|high",
  "teamwork_risk": "low|low_medium|medium|medium_high|high",
  "attitude_risk": "low|low_medium|medium|medium_high|high",
  "training_potential": "low|medium|high",
  "communication_quality": "...",
  "english_khmer_note": "...",
  "process_following_score": 0.0-1.0,
  "intake_behavior_summary": "...",
  "quiz_behavior_summary": "...",
  "parte_summary": "...",
  "role_fit": "...",
  "role_fit_reasoning": "...",
  "suggested_offer": {{
    "recommended_base_salary": 0,
    "acceptable_range": [0, 0],
    "hours_per_day": 9,
    "bonus": 0,
    "food_allowance_daily_riel": 0,
    "reasoning": "...",
    "do_not_exceed_without_owner_review": 0,
    "note": "..."
  }},
  "must_verify_in_person": [
    {{"topic": "...", "question": "...", "evidence_refs": [...]}}
  ],
  "trial_watchlist_with_behaviors": [
    {{"watch": "...", "evidence_refs": [...], "observable_test": "..."}}
  ],
  "targeted_message_points": [
    {{
      "point_number": 1,
      "topic": "...",
      "severity": "low|medium|high|critical",
      "goal": "...",
      "evidence_refs": [...],
      "english": "...",
      "khmer_pending": true
    }}
  ],
  "required_before_offer": ["...", "..."],
  "final_owner_summary": "3-5 sentences answering: who is this person, biggest risk, biggest upside, recommendation, what to do next"
}}
"""

# ── Minimal JSON schema validation ────────────────────────────────────────────
_REQUIRED_TOP_LEVEL = [
    "overall_recommendation", "confidence", "score_vs_judgment_note",
    "evidence_based_findings", "who_is_this_person", "targeted_message_points",
    "suggested_offer", "required_before_offer", "final_owner_summary",
]

def validate_assessment_json(output: dict) -> tuple[bool, list[str]]:
    """
    Check required fields and that every evidence_based_finding has evidence_refs.
    Returns (is_valid, list_of_errors).
    """
    errors = []
    for field in _REQUIRED_TOP_LEVEL:
        if field not in output:
            errors.append(f"Missing required field: {field}")

    for i, finding in enumerate(output.get("evidence_based_findings", [])):
        if not finding.get("evidence_refs"):
            errors.append(
                f"evidence_based_findings[{i}] missing evidence_refs — "
                f"every finding must cite its source"
            )

    for i, pt in enumerate(output.get("targeted_message_points", [])):
        if not pt.get("evidence_refs"):
            errors.append(f"targeted_message_points[{i}] missing evidence_refs")
        if not pt.get("english"):
            errors.append(f"targeted_message_points[{i}] missing english text")

    offer = output.get("suggested_offer", {})
    if offer.get("recommended_base_salary", 0) <= 0:
        errors.append("suggested_offer.recommended_base_salary must be > 0")

    return len(errors) == 0, errors


async def run_final_hiring_assessment(package: dict, max_retries: int = 2) -> dict:
    """
    Send evidence package to the configured model (Opus by default).
    Returns the validated assessment dict.
    Raises on failure after retries.

    Khmer is NOT generated here. Only English targeted message points.
    Khmer rewrite is a separate call.
    """
    from shared.ai_client import _get_client

    package_json = json.dumps(package, ensure_ascii=False, indent=2)
    user_msg = _ASSESSMENT_USER_TEMPLATE.format(
        package_json=package_json,
        model=ASSESSMENT_MODEL,
        prompt_version=ASSESSMENT_PROMPT_VERSION,
        rubric_version=RUBRIC_VERSION,
    )

    last_error = None
    for attempt_num in range(max_retries + 1):
        try:
            client = _get_client()
            resp = await client.messages.create(
                model=ASSESSMENT_MODEL,
                max_tokens=8192,
                system=_ASSESSMENT_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw_text = resp.content[0].text.strip()

            # Strip markdown fences if model wrapped output
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                raw_text = "\n".join(
                    l for l in lines
                    if not l.strip().startswith("```")
                )

            output = json.loads(raw_text)
            is_valid, errors = validate_assessment_json(output)

            if not is_valid:
                if attempt_num < max_retries:
                    logger.warning(
                        "Assessment JSON invalid (attempt %d/%d): %s",
                        attempt_num + 1, max_retries + 1, errors
                    )
                    continue
                else:
                    raise ValueError(
                        f"Assessment JSON still invalid after {max_retries + 1} attempts: {errors}"
                    )

            output["_meta"] = {
                "model": ASSESSMENT_MODEL,
                "prompt_version": ASSESSMENT_PROMPT_VERSION,
                "rubric_version": RUBRIC_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "attempt_num": attempt_num,
            }
            return output

        except json.JSONDecodeError as e:
            last_error = e
            if attempt_num < max_retries:
                logger.warning("JSON decode failed attempt %d: %s", attempt_num + 1, e)
            continue
        except Exception as e:
            last_error = e
            raise

    raise RuntimeError(
        f"run_final_hiring_assessment failed after {max_retries + 1} attempts: {last_error}"
    )


async def run_khmer_rewrite(english_points: list[dict]) -> list[dict]:
    """
    Dedicated Khmer rewrite pass — separate from the main assessment call.
    Returns the same points with khmer field added.
    Caller MUST run khmer_validator on each point before storing or sending.

    If Khmer fails validation after 2 retries, returns khmer=None,
    khmer_status='validation_failed' so caller can flag for manual translation.
    """
    from shared.ai_client import _get_client
    from hire_bot.khmer_validator import validate_khmer

    if not english_points:
        return english_points

    english_list = "\n\n".join(
        f"Point {pt['point_number']}: {pt['english']}"
        for pt in english_points
    )

    system = (
        "You translate English correction/feedback messages to clean Cambodian "
        "workplace Khmer.\n\n"
        "Rules:\n"
        "- Use ប្អូន register for applicants/junior staff\n"
        "- Short sentences — max 3-4 lines per point\n"
        "- Direct and fair — not humiliating, not robotic\n"
        "- NO broken spacing inside Khmer compound characters\n"
        "- Keep subscript markers (្) immediately attached to following consonant\n"
        "- Do not split words: ខ្ញុំ not ខ្ ញុំ\n"
        "- Business name stays in English: The Wine Bakery\n"
        "- Output ONLY valid JSON: {\"translations\": [{\"point_number\": N, \"khmer\": \"...\"}]}"
    )
    user = f"Translate these correction points to clean Khmer:\n\n{english_list}"

    result = [dict(pt) for pt in english_points]

    for attempt_num in range(2):
        try:
            client = _get_client()
            resp = await client.messages.create(
                model=ASSESSMENT_MODEL,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            raw = resp.content[0].text.strip()
            if raw.startswith("```"):
                raw = "\n".join(l for l in raw.split("\n") if not l.strip().startswith("```"))
            parsed = json.loads(raw)
            translations = {t["point_number"]: t["khmer"] for t in parsed["translations"]}

            # Validate each translated point
            all_valid = True
            for pt in result:
                khmer = translations.get(pt["point_number"], "")
                v = validate_khmer(khmer)
                if v["passed"]:
                    pt["khmer"] = khmer
                    pt["khmer_status"] = "passed"
                else:
                    pt["khmer"] = None
                    pt["khmer_status"] = "validation_failed"
                    pt["khmer_violations"] = v["violations"]
                    all_valid = False

            if all_valid:
                return result

            if attempt_num == 0:
                logger.warning("Khmer validation failed on attempt 1, retrying")
                continue

        except Exception as e:
            logger.error("run_khmer_rewrite failed: %s", e)
            for pt in result:
                if "khmer" not in pt:
                    pt["khmer"] = None
                    pt["khmer_status"] = "generation_error"

    return result


def store_assessment(
    package: dict,
    assessment: dict,
    attempt_id: int,
    intake_id: int | None,
) -> int:
    """Store the Opus assessment. Returns assessment_id."""
    import psycopg2
    from secrets import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO hiring_ai_assessments
                (candidate_id, intake_id, attempt_id, assessment_mode,
                 provider, model, prompt_version, rubric_version,
                 input_package_json, output_json, output_valid,
                 recommendation, confidence, critical_signal_count,
                 created_at)
            VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s, now())
            RETURNING id
        """, (
            package["candidate"]["candidate_id"],
            intake_id,
            attempt_id,
            package.get("assessment_mode", "applicant_hiring_screen"),
            ASSESSMENT_PROVIDER,
            ASSESSMENT_MODEL,
            ASSESSMENT_PROMPT_VERSION,
            RUBRIC_VERSION,
            json.dumps(package, ensure_ascii=False),
            json.dumps(assessment, ensure_ascii=False),
            True,  # already validated before calling store
            assessment.get("overall_recommendation"),
            assessment.get("confidence"),
            len(assessment.get("critical_signal_hits", [])),
        ))
        assessment_id = cur.fetchone()[0]
        conn.commit()
        return assessment_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close(); conn.close()
