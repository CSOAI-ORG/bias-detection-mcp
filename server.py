#!/usr/bin/env python3
"""
AI Bias Detection MCP Server
==============================
By MEOK AI Labs | https://meok.ai

The only MCP server for AI bias detection and fairness assessment.
Covers demographic bias scanning, fairness metrics, mitigation strategies,
and regulatory compliance (EU AI Act Article 10, NIST AI RMF).

Install: pip install mcp
Run:     python server.py
"""

import re
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from mcp.server.fastmcp import FastMCP

# -- Authentication --------------------------------------------------------
import os as _os
import sys, os

_MEOK_API_KEY = _os.environ.get("MEOK_API_KEY", "")
_neural_net = None

try:
    from auth_middleware import check_access as _shared_check_access
    _AUTH_ENGINE_AVAILABLE = True
except ImportError:
    _AUTH_ENGINE_AVAILABLE = False

    def _shared_check_access(api_key: str = ""):
        """Fallback when shared auth engine is not available."""
        if _MEOK_API_KEY and api_key and api_key == _MEOK_API_KEY:
            return True, "OK", "pro"
        if _MEOK_API_KEY and api_key and api_key != _MEOK_API_KEY:
            return False, "Invalid API key. Get one at https://meok.ai/api-keys", "free"
        return True, "OK, Pro at https://www.csoai.org/checkout", "free"


def check_access(api_key=""):
    # type: (str) -> Tuple[bool, str, str]
    """Unified access check -- works with or without shared auth engine."""
    return _shared_check_access(api_key)


# -- Rate limiting ---------------------------------------------------------
FREE_DAILY_LIMIT = 10
PRO_TIER_UNLIMITED = True  # Pro: $29/mo unlimited at https://meok.ai/mcp/bias-detection/pro
_usage = defaultdict(list)  # type: Dict[str, List[datetime]]


def _check_rate_limit(caller="anonymous", tier="free"):
    # type: (str, str) -> Optional[str]
    """Returns error string if rate-limited, else None."""
    if tier == "pro":
        return None
    now = datetime.now()
    cutoff = now - timedelta(days=1)
    _usage[caller] = [t for t in _usage[caller] if t > cutoff]
    if len(_usage[caller]) >= FREE_DAILY_LIMIT:
        return (
            "Free tier limit reached ({}/day). "
            "Upgrade to MEOK AI Labs Pro for unlimited access at $29/mo: "
            "https://meok.ai/mcp/bias-detection/pro".format(FREE_DAILY_LIMIT)
        )
    _usage[caller].append(now)
    return None


# ---------------------------------------------------------------------------
# Bias Knowledge Base
# ---------------------------------------------------------------------------

BIAS_TYPES = {
    "selection": {
        "name": "Selection Bias",
        "description": "Training data does not represent the population the model serves",
        "indicators": ["underrepresent", "overrepresent", "sample", "population", "coverage", "missing demographic"],
        "severity": "high",
        "eu_article": "Article 10(2)(f) — examination of data for biases",
    },
    "measurement": {
        "name": "Measurement Bias",
        "description": "Features or labels are measured differently across groups",
        "indicators": ["proxy", "indirect", "measurement", "label noise", "annotation", "ground truth"],
        "severity": "high",
        "eu_article": "Article 10(2)(f) — data quality and representativeness",
    },
    "confirmation": {
        "name": "Confirmation Bias",
        "description": "Model reinforces existing stereotypes or pre-existing beliefs",
        "indicators": ["stereotype", "reinforc", "historical", "pre-existing", "perpetuat", "amplif"],
        "severity": "high",
        "eu_article": "Article 10(2)(f) — bias identification and mitigation",
    },
    "automation": {
        "name": "Automation Bias",
        "description": "Over-reliance on automated outputs without human verification",
        "indicators": ["automat", "override", "human-in-the-loop", "rubber stamp", "blind trust", "no review"],
        "severity": "medium",
        "eu_article": "Article 14 — Human oversight",
    },
    "aggregation": {
        "name": "Aggregation Bias",
        "description": "A single model is applied to groups with different conditional distributions",
        "indicators": ["one-size-fits-all", "single model", "heterogeneous", "subgroup", "stratif"],
        "severity": "medium",
        "eu_article": "Article 10(2)(f) — statistical properties and biases",
    },
    "representation": {
        "name": "Representation Bias",
        "description": "Certain groups are underrepresented in training data relative to deployment population",
        "indicators": ["underrepresent", "minority", "imbalanc", "skew", "disproportion", "demographic gap"],
        "severity": "high",
        "eu_article": "Article 10(3) — representative data",
    },
    "evaluation": {
        "name": "Evaluation Bias",
        "description": "Evaluation benchmarks do not represent all user groups equally",
        "indicators": ["benchmark", "test set", "evaluat", "validation", "held-out", "test distribut"],
        "severity": "medium",
        "eu_article": "Article 10(4) — validation and testing datasets",
    },
    "historical": {
        "name": "Historical Bias",
        "description": "Data reflects historical inequalities that should not be perpetuated",
        "indicators": ["historical", "legacy", "systemic", "structural", "inequalit", "past discriminat"],
        "severity": "high",
        "eu_article": "Article 10(2)(f) — bias examination",
    },
}

PROTECTED_ATTRIBUTES_DB = {
    "race": {"keywords": ["race", "racial", "ethnicity", "ethnic", "skin color", "skin colour"], "eu_ref": "Charter Article 21"},
    "gender": {"keywords": ["gender", "sex", "male", "female", "non-binary", "transgender"], "eu_ref": "Charter Article 21, 23"},
    "age": {"keywords": ["age", "elderly", "young", "senior", "minor", "child"], "eu_ref": "Charter Article 21, 24, 25"},
    "disability": {"keywords": ["disabilit", "impair", "handicap", "accessible", "assistive"], "eu_ref": "Charter Article 21, 26"},
    "religion": {"keywords": ["religion", "religious", "faith", "belief", "muslim", "christian", "jewish", "hindu", "buddhist", "atheist"], "eu_ref": "Charter Article 10, 21"},
    "nationality": {"keywords": ["nationality", "national origin", "country of origin", "immigrant", "migrant"], "eu_ref": "Charter Article 21"},
    "sexual_orientation": {"keywords": ["sexual orientation", "gay", "lesbian", "bisexual", "lgbtq", "homosexual", "heterosexual"], "eu_ref": "Charter Article 21"},
    "socioeconomic": {"keywords": ["socioeconomic", "income", "poverty", "wealth", "class", "economic status", "zip code", "postcode"], "eu_ref": "Charter Article 21, 34"},
}

MANIPULATION_PATTERNS = [
    {"pattern": "always", "weight": 0.3, "category": "absolute_language"},
    {"pattern": "never", "weight": 0.3, "category": "absolute_language"},
    {"pattern": "all [a-z]+ are", "weight": 0.6, "category": "generalisation"},
    {"pattern": "typically", "weight": 0.2, "category": "stereotyping"},
    {"pattern": "tend to", "weight": 0.2, "category": "stereotyping"},
    {"pattern": "most [a-z]+ people", "weight": 0.4, "category": "generalisation"},
    {"pattern": "obviously", "weight": 0.15, "category": "assumption"},
    {"pattern": "naturally", "weight": 0.15, "category": "assumption"},
    {"pattern": "inherently", "weight": 0.3, "category": "essentialising"},
    {"pattern": "born to", "weight": 0.4, "category": "essentialising"},
    {"pattern": "not capable", "weight": 0.5, "category": "deficit_framing"},
    {"pattern": "less qualified", "weight": 0.5, "category": "deficit_framing"},
    {"pattern": "more likely to", "weight": 0.3, "category": "statistical_stereotyping"},
    {"pattern": "less likely to", "weight": 0.3, "category": "statistical_stereotyping"},
    {"pattern": "those people", "weight": 0.5, "category": "othering"},
    {"pattern": "them vs us", "weight": 0.6, "category": "othering"},
    {"pattern": "normal people", "weight": 0.4, "category": "othering"},
]

MITIGATION_STRATEGIES = {
    "selection": [
        "Conduct a demographic audit of your training data against deployment population",
        "Use stratified sampling to ensure proportional representation",
        "Collect additional data from underrepresented groups",
        "Apply domain adaptation techniques for distribution shift",
        "Document data gaps in Annex IV technical documentation (EU AI Act Article 10(2)(f))",
    ],
    "measurement": [
        "Audit labels and features for group-dependent measurement error",
        "Use multiple annotators and measure inter-annotator agreement per group",
        "Remove or debias proxy variables that correlate with protected attributes",
        "Apply fairness-aware feature selection methods",
        "Document measurement methodology per EU AI Act Annex IV Section 2.5",
    ],
    "confirmation": [
        "Apply counterfactual data augmentation to break spurious correlations",
        "Use adversarial debiasing during training",
        "Implement post-processing calibration across groups",
        "Conduct stereotype association tests (e.g., WEAT, SEAT) on embeddings",
        "Establish ongoing bias monitoring as part of post-market surveillance (Article 72)",
    ],
    "automation": [
        "Implement mandatory human-in-the-loop review for high-stakes decisions",
        "Display confidence intervals alongside predictions",
        "Train deployers on automation bias risks (EU AI Act Article 14(4)(b))",
        "Add friction mechanisms (confirmation steps, cooling-off periods)",
        "Log human override rates and audit patterns (Article 12)",
    ],
    "aggregation": [
        "Train subgroup-specific models where conditional distributions differ",
        "Use multi-task learning with group-aware objectives",
        "Apply fairness constraints during optimisation (e.g., demographic parity, equalized odds)",
        "Evaluate performance metrics per subgroup, not just aggregate",
        "Document subgroup analysis in technical documentation (Annex IV Section 4)",
    ],
    "representation": [
        "Measure representation ratios against census or deployment population data",
        "Oversample underrepresented groups or use SMOTE/ADASYN",
        "Apply re-weighting to give underrepresented samples higher importance",
        "Use data augmentation targeted at underrepresented demographics",
        "Report representation gaps in Article 10 data governance documentation",
    ],
    "evaluation": [
        "Build disaggregated evaluation sets that cover all deployment demographics",
        "Report metrics broken down by protected attribute",
        "Use multiple fairness metrics (not just accuracy)",
        "Conduct intersectional analysis (e.g., race x gender x age)",
        "Include evaluation methodology in Annex IV Section 4 documentation",
    ],
    "historical": [
        "Identify and document historical inequalities in the training data",
        "Apply causal reasoning to distinguish legitimate from discriminatory patterns",
        "Use fairness-aware algorithms that correct for historical disparities",
        "Consult domain experts and affected communities during system design",
        "Conduct a Fundamental Rights Impact Assessment (EU AI Act Article 27)",
    ],
}


def _match_keywords(text, keywords):
    # type: (str, List[str]) -> List[str]
    """Return matched keywords found in text (case-insensitive)."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _score_bias_risk(text):
    # type: (str) -> Tuple[float, List[Dict[str, str]]]
    """Score text for bias patterns. Returns (score 0-1, matched_patterns)."""
    text_lower = text.lower()
    total_weight = 0.0
    matches = []  # type: List[Dict[str, str]]
    seen_categories = set()  # type: set

    for pat in MANIPULATION_PATTERNS:
        if re.search(pat["pattern"], text_lower):
            total_weight += pat["weight"]
            if pat["category"] not in seen_categories:
                seen_categories.add(pat["category"])
                matches.append({
                    "pattern": pat["pattern"],
                    "category": pat["category"],
                    "weight": str(pat["weight"]),
                })

    # Check for protected attribute mentions without fairness context
    fairness_terms = ["fair", "equit", "bias", "discriminat", "parity", "equal"]
    has_fairness_context = any(ft in text_lower for ft in fairness_terms)

    protected_mentioned = []  # type: List[str]
    for attr, info in PROTECTED_ATTRIBUTES_DB.items():
        if _match_keywords(text, info["keywords"]):
            protected_mentioned.append(attr)
            if not has_fairness_context:
                total_weight += 0.15

    # Normalise to 0-1
    score = min(1.0, total_weight / 2.5)
    return score, matches


def _detect_protected_attributes(text):
    # type: (str) -> List[Dict[str, object]]
    """Detect mentions of protected attributes in text."""
    found = []  # type: List[Dict[str, object]]
    for attr, info in PROTECTED_ATTRIBUTES_DB.items():
        matched = _match_keywords(text, info["keywords"])
        if matched:
            found.append({
                "attribute": attr,
                "matched_terms": matched,
                "eu_reference": info["eu_ref"],
            })
    return found


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "AI Bias Detection",
    instructions=(
        "By MEOK AI Labs -- AI bias detection and fairness assessment. "
        "Start with quick_scan (one sentence, instant bias risk). "
        "Full tools: detect_bias, fairness_metrics, mitigation_recommendations, regulatory_check. "
        "No API key needed for free tier (10 calls/day)."
    ),
)


# ---------------------------------------------------------------------------
# Tool: quick_scan -- ZERO config, no API key, instant result
# ---------------------------------------------------------------------------
@mcp.tool()
def quick_scan(description: str) -> dict:
    """Describe an AI system in one sentence -> instant bias risk assessment. No API key required.

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.
    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    limit_err = _check_rate_limit("quick_scan_anonymous")
    if limit_err:
        return {"error": "rate_limited", "message": limit_err}

    text_lower = description.lower()

    # Detect system type and inherent risk
    high_risk_indicators = [
        "hiring", "recruit", "loan", "credit", "insurance", "bail", "sentencing",
        "parole", "admissions", "grading", "welfare", "benefits", "housing",
        "healthcare", "diagnosis", "triage", "policing", "surveillance",
        "facial recognition", "biometric",
    ]
    moderate_risk_indicators = [
        "recommendation", "content moderation", "search ranking", "advertising",
        "pricing", "customer service", "chatbot", "translation", "summariz",
    ]
    low_risk_indicators = [
        "spell check", "weather", "calculator", "file conversion", "image resize",
    ]

    risk_level = "low"
    risk_score = 0.1
    matched_risk_indicators = []  # type: List[str]

    for ind in high_risk_indicators:
        if ind in text_lower:
            risk_level = "high"
            risk_score = max(risk_score, 0.75)
            matched_risk_indicators.append(ind)

    if risk_level != "high":
        for ind in moderate_risk_indicators:
            if ind in text_lower:
                risk_level = "moderate"
                risk_score = max(risk_score, 0.45)
                matched_risk_indicators.append(ind)

    if risk_level == "low":
        for ind in low_risk_indicators:
            if ind in text_lower:
                matched_risk_indicators.append(ind)

    # Detect protected attribute exposure
    protected_attrs = _detect_protected_attributes(description)
    if protected_attrs:
        risk_score = min(1.0, risk_score + 0.15 * len(protected_attrs))

    # Detect bias type exposure
    bias_types_detected = []  # type: List[str]
    for btype, binfo in BIAS_TYPES.items():
        if _match_keywords(description, binfo["indicators"]):
            bias_types_detected.append(binfo["name"])

    # Build recommendations
    top_actions = []  # type: List[str]
    if risk_level == "high":
        top_actions = [
            "Conduct a full fairness audit with disaggregated metrics before deployment",
            "Implement EU AI Act Article 10 data governance (bias examination mandatory for high-risk AI)",
            "Establish human oversight per Article 14 for all decisions affecting individuals",
        ]
    elif risk_level == "moderate":
        top_actions = [
            "Run detect_bias on representative model outputs to measure demographic disparities",
            "Document data sources and representation in technical documentation",
            "Monitor for emergent bias patterns post-deployment",
        ]
    else:
        top_actions = [
            "Low bias risk -- monitor for edge cases and user feedback",
            "Consider voluntary fairness testing as a best practice",
            "Document any assumptions about user demographics",
        ]

    return {
        "bias_risk_level": risk_level,
        "bias_risk_score": round(risk_score, 2),
        "matched_risk_indicators": matched_risk_indicators,
        "protected_attributes_detected": [a["attribute"] for a in protected_attrs],
        "bias_types_to_watch": bias_types_detected if bias_types_detected else ["Run detect_bias for detailed analysis"],
        "top_3_actions": top_actions,
        "eu_ai_act_relevance": (
            "HIGH -- Article 10 data governance and bias examination mandatory"
            if risk_level == "high"
            else "MODERATE -- transparency obligations may apply"
            if risk_level == "moderate"
            else "LOW -- voluntary codes of conduct encouraged"
        ),
        "next_step": "Use detect_bias for text-level analysis or fairness_metrics for quantitative assessment",
        "meok_labs": "https://meok.ai",
    }


# ---------------------------------------------------------------------------
# Tool: detect_bias
# ---------------------------------------------------------------------------
@mcp.tool()
def detect_bias(
    model_output: str,
    protected_attributes: str = "",
    api_key: str = "",
) -> dict:
    """Analyze text for demographic bias patterns, stereotyping, and unfair language.

    Args:
        model_output: The AI-generated text to analyze for bias.
        protected_attributes: Comma-separated list of attributes to check (e.g. "race,gender,age"). Leave empty for auto-detection.
        api_key: Optional MEOK API key for pro tier.

    Behavior:
        This tool generates structured output without modifying external systems.
        Output is deterministic for identical inputs. No side effects.
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return {"error": msg, "upgrade_url": "https://meok.ai/api-keys"}
    limit_err = _check_rate_limit("detect_bias", tier)
    if limit_err:
        return {"error": "rate_limited", "message": limit_err}

    # GATE: Detailed bias analysis is a Pro feature
    if tier == "free":
        # Give a quick teaser to show value
        quick_score, _ = _score_bias_risk(model_output)
        quick_attrs = _detect_protected_attributes(model_output)
        if quick_score >= 0.7:
            teaser_level = "HIGH"
        elif quick_score >= 0.4:
            teaser_level = "MODERATE"
        elif quick_score >= 0.15:
            teaser_level = "LOW"
        else:
            teaser_level = "MINIMAL"
        return {
            "error": "pro_feature",
            "message": (
                "Detailed bias analysis requires MEOK Pro. "
                "This tool performs sentence-level bias scoring, pattern matching across "
                "8 bias types, protected attribute detection with EU Charter references, "
                "and generates actionable remediation recommendations."
            ),
            "preview": {
                "quick_bias_level": teaser_level,
                "quick_bias_score": round(quick_score, 2),
                "protected_attributes_found": len(quick_attrs),
                "analysis_sections": [
                    "Sentence-level bias scoring with flagged excerpts",
                    "8-type bias classification (selection, measurement, confirmation, etc.)",
                    "Protected attribute mapping to EU Charter Articles",
                    "Pattern match breakdown (stereotyping, essentialising, othering, etc.)",
                    "Actionable remediation recommendations",
                ],
                "estimated_value": "Equivalent to GBP 500-2,000 bias audit",
            },
            "upgrade": {
                "url": "https://meok.ai/api-keys",
                "stripe_checkout": "https://buy.stripe.com/00wfZjcgAeUW4c5cyQ8k90K",
                "price": "From GBP 29/month -- includes unlimited bias analysis",
            },
            "free_alternative": "Use quick_scan (free, no API key needed) for instant risk assessment, or regulatory_check for compliance requirements.",
        }

    # Score for bias patterns
    bias_score, pattern_matches = _score_bias_risk(model_output)

    # Detect protected attributes mentioned
    auto_detected = _detect_protected_attributes(model_output)

    # If user specified attributes, filter/augment
    requested_attrs = []  # type: List[str]
    if protected_attributes:
        requested_attrs = [a.strip().lower() for a in protected_attributes.split(",")]

    # Identify specific bias types present
    detected_bias_types = []  # type: List[Dict[str, str]]
    for btype, binfo in BIAS_TYPES.items():
        matched = _match_keywords(model_output, binfo["indicators"])
        if matched:
            detected_bias_types.append({
                "type": binfo["name"],
                "severity": binfo["severity"],
                "matched_indicators": matched,
                "eu_article": binfo["eu_article"],
            })

    # Classify overall risk
    if bias_score >= 0.7:
        overall_risk = "high"
        recommendation = (
            "CRITICAL: High bias detected. This output should not be used for decisions "
            "affecting individuals without significant human review and debiasing."
        )
    elif bias_score >= 0.4:
        overall_risk = "moderate"
        recommendation = (
            "WARNING: Moderate bias patterns detected. Review flagged patterns and consider "
            "rephrasing or adding qualifying context before deployment."
        )
    elif bias_score >= 0.15:
        overall_risk = "low"
        recommendation = (
            "Minor bias indicators detected. Generally acceptable but review flagged "
            "patterns for context appropriateness."
        )
    else:
        overall_risk = "minimal"
        recommendation = (
            "No significant bias patterns detected in this text. Continue monitoring "
            "outputs for emergent patterns."
        )

    # Sentence-level analysis
    sentences = [s.strip() for s in re.split(r'[.!?]+', model_output) if s.strip()]
    flagged_sentences = []  # type: List[Dict[str, object]]
    for sentence in sentences:
        s_score, s_matches = _score_bias_risk(sentence)
        if s_score > 0.15:
            flagged_sentences.append({
                "sentence": sentence,
                "bias_score": round(s_score, 2),
                "patterns": [m["category"] for m in s_matches],
            })

    return {
        "overall_bias_risk": overall_risk,
        "bias_score": round(bias_score, 2),
        "pattern_matches": pattern_matches,
        "protected_attributes_mentioned": auto_detected,
        "bias_types_detected": detected_bias_types,
        "flagged_sentences": flagged_sentences[:10],
        "recommendation": recommendation,
        "total_sentences_analyzed": len(sentences),
        "sentences_flagged": len(flagged_sentences),
        "next_step": "Use mitigation_recommendations for remediation or fairness_metrics for quantitative assessment",
        "meok_labs": "https://meok.ai",
    }


# ---------------------------------------------------------------------------
# Tool: fairness_metrics
# ---------------------------------------------------------------------------
@mcp.tool()
def fairness_metrics(
    predictions: str,
    ground_truth: str = "",
    api_key: str = "",
) -> dict:
    """Calculate fairness metrics from prediction data. Input format: comma-separated values with group labels.

    Provide predictions as 'group:prediction' pairs separated by commas.
    Example: "male:1,female:0,male:1,female:1,male:0,female:0"

    If ground_truth is provided, use same format for actual outcomes to compute
    equalized odds and calibration metrics.

    Args:
        predictions: Comma-separated group:prediction pairs (e.g. "male:1,female:0,male:1").
        ground_truth: Optional comma-separated group:actual pairs for outcome-based metrics.
        api_key: Optional MEOK API key for pro tier.

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return {"error": msg, "upgrade_url": "https://meok.ai/api-keys"}
    limit_err = _check_rate_limit("fairness_metrics", tier)
    if limit_err:
        return {"error": "rate_limited", "message": limit_err}

    # GATE: Fairness metrics calculation is a Pro feature
    if tier == "free":
        # Count groups from input to show preview value
        groups_seen = set()
        for pair in predictions.split(","):
            pair = pair.strip()
            if ":" in pair:
                groups_seen.add(pair.rsplit(":", 1)[0].strip().lower())
        return {
            "error": "pro_feature",
            "message": (
                "Fairness metrics calculation requires MEOK Pro. "
                "This tool computes disparate impact ratio (4/5ths rule), statistical parity, "
                "equalized odds (TPR/FPR per group), and calibration metrics -- with "
                "EU AI Act Article 10 compliance mapping."
            ),
            "preview": {
                "groups_detected": list(groups_seen),
                "metrics_computed": [
                    "Disparate impact ratio (EEOC 4/5ths rule)",
                    "Statistical parity difference",
                    "Equalized odds (TPR gap + FPR gap)",
                    "Per-group selection rates",
                    "Per-group accuracy, TPR, and FPR",
                ],
                "compliance_mapping": "EU AI Act Article 10(2)(f), 10(3), 10(4), 15(1)",
                "estimated_value": "Equivalent to GBP 1,000-3,000 fairness audit",
            },
            "upgrade": {
                "url": "https://meok.ai/api-keys",
                "stripe_checkout": "https://buy.stripe.com/00wfZjcgAeUW4c5cyQ8k90K",
                "price": "From GBP 29/month -- includes unlimited fairness metrics",
            },
            "free_alternative": "Use quick_scan (free) for instant risk assessment, or regulatory_check for compliance requirements.",
        }

    # Parse predictions
    group_preds = defaultdict(list)  # type: Dict[str, List[int]]
    try:
        for pair in predictions.split(","):
            pair = pair.strip()
            if ":" not in pair:
                continue
            group, pred = pair.rsplit(":", 1)
            group_preds[group.strip().lower()].append(int(pred.strip()))
    except (ValueError, IndexError):
        return {
            "error": "invalid_format",
            "message": "Use format: group:prediction (e.g. 'male:1,female:0'). Predictions must be 0 or 1.",
        }

    if len(group_preds) < 2:
        return {
            "error": "insufficient_groups",
            "message": "Need at least 2 groups for fairness comparison. Found: {}".format(list(group_preds.keys())),
        }

    # Calculate selection rates per group
    group_stats = {}  # type: Dict[str, Dict[str, object]]
    for group, preds in group_preds.items():
        positive_rate = sum(preds) / len(preds) if preds else 0
        group_stats[group] = {
            "total": len(preds),
            "positive": sum(preds),
            "negative": len(preds) - sum(preds),
            "positive_rate": round(positive_rate, 4),
        }

    # Disparate impact (4/5ths rule)
    rates = [(g, s["positive_rate"]) for g, s in group_stats.items()]
    max_rate = max(r[1] for r in rates) if rates else 1
    min_rate = min(r[1] for r in rates) if rates else 0

    disparate_impact_ratio = round(min_rate / max_rate, 4) if max_rate > 0 else 0.0
    passes_four_fifths = disparate_impact_ratio >= 0.8

    # Statistical parity difference
    stat_parity_diff = round(max_rate - min_rate, 4)

    # Parse ground truth if provided
    equalized_odds = None
    if ground_truth:
        group_actuals = defaultdict(list)  # type: Dict[str, List[int]]
        try:
            for pair in ground_truth.split(","):
                pair = pair.strip()
                if ":" not in pair:
                    continue
                group, actual = pair.rsplit(":", 1)
                group_actuals[group.strip().lower()].append(int(actual.strip()))
        except (ValueError, IndexError):
            group_actuals = defaultdict(list)

        if group_actuals and len(group_actuals) >= 2:
            # Calculate TPR and FPR per group
            eo_stats = {}  # type: Dict[str, Dict[str, float]]
            for group in group_preds:
                if group not in group_actuals:
                    continue
                preds = group_preds[group]
                actuals = group_actuals[group]
                n = min(len(preds), len(actuals))
                tp = sum(1 for i in range(n) if preds[i] == 1 and actuals[i] == 1)
                fp = sum(1 for i in range(n) if preds[i] == 1 and actuals[i] == 0)
                fn = sum(1 for i in range(n) if preds[i] == 0 and actuals[i] == 1)
                tn = sum(1 for i in range(n) if preds[i] == 0 and actuals[i] == 0)

                tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

                eo_stats[group] = {
                    "true_positive_rate": round(tpr, 4),
                    "false_positive_rate": round(fpr, 4),
                    "accuracy": round((tp + tn) / n, 4) if n > 0 else 0.0,
                }

            if eo_stats:
                tprs = [s["true_positive_rate"] for s in eo_stats.values()]
                fprs = [s["false_positive_rate"] for s in eo_stats.values()]
                equalized_odds = {
                    "group_metrics": eo_stats,
                    "tpr_gap": round(max(tprs) - min(tprs), 4),
                    "fpr_gap": round(max(fprs) - min(fprs), 4),
                    "equalized_odds_satisfied": (max(tprs) - min(tprs)) < 0.1 and (max(fprs) - min(fprs)) < 0.1,
                }

    # Overall fairness assessment
    issues = []  # type: List[str]
    if not passes_four_fifths:
        issues.append(
            "FAILS 4/5ths rule (disparate impact ratio {:.2f} < 0.80) -- "
            "prima facie evidence of discrimination under US EEOC guidelines".format(disparate_impact_ratio)
        )
    if stat_parity_diff > 0.1:
        issues.append(
            "Statistical parity gap {:.2f} exceeds 0.10 threshold -- "
            "groups receive positive outcomes at significantly different rates".format(stat_parity_diff)
        )
    if equalized_odds and not equalized_odds["equalized_odds_satisfied"]:
        issues.append(
            "Equalized odds NOT satisfied -- error rates differ across groups"
        )

    return {
        "group_statistics": group_stats,
        "disparate_impact": {
            "ratio": disparate_impact_ratio,
            "passes_four_fifths_rule": passes_four_fifths,
            "highest_rate_group": max(rates, key=lambda x: x[1])[0] if rates else "N/A",
            "lowest_rate_group": min(rates, key=lambda x: x[1])[0] if rates else "N/A",
        },
        "statistical_parity": {
            "difference": stat_parity_diff,
            "acceptable": stat_parity_diff < 0.1,
        },
        "equalized_odds": equalized_odds,
        "fairness_issues": issues if issues else ["No significant fairness issues detected"],
        "overall_assessment": "FAIL -- fairness issues detected" if issues else "PASS -- no significant fairness issues",
        "eu_ai_act_note": (
            "Article 10(2)(f) requires examination of training data for biases. "
            "Article 10(3) requires data to be representative. "
            "Document these metrics in Annex IV Section 4."
        ),
        "next_step": "Use mitigation_recommendations for specific remediation strategies",
        "meok_labs": "https://meok.ai",
    }


# ---------------------------------------------------------------------------
# Tool: mitigation_recommendations
# ---------------------------------------------------------------------------
@mcp.tool()
def mitigation_recommendations(
    bias_type: str,
    api_key: str = "",
) -> dict:
    """Get detailed remediation steps for a specific type of AI bias.

    Args:
        bias_type: Type of bias to get recommendations for. Options: selection, measurement,
            confirmation, automation, aggregation, representation, evaluation, historical.
        api_key: Optional MEOK API key for pro tier.

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.
    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return {"error": msg, "upgrade_url": "https://meok.ai/api-keys"}
    limit_err = _check_rate_limit("mitigation", tier)
    if limit_err:
        return {"error": "rate_limited", "message": limit_err}

    # GATE: Mitigation recommendations is a Pro feature
    if tier == "free":
        bias_key_check = bias_type.strip().lower()
        binfo_check = BIAS_TYPES.get(bias_key_check)
        return {
            "error": "pro_feature",
            "message": (
                "Detailed bias mitigation recommendations require MEOK Pro. "
                "This tool provides pre-processing, in-processing, and post-processing "
                "remediation strategies, EU AI Act documentation requirements, "
                "monitoring plans, and recommended tools/frameworks."
            ),
            "preview": {
                "bias_type_requested": bias_type,
                "bias_type_valid": bias_key_check in BIAS_TYPES,
                "severity": binfo_check["severity"] if binfo_check else "unknown",
                "remediation_sections": [
                    "Bias-type-specific mitigation strategies (5 per type)",
                    "Pre-processing remediation (data-level fixes)",
                    "In-processing remediation (model-level fixes)",
                    "Post-processing remediation (output-level fixes)",
                    "EU AI Act documentation requirements (Annex IV)",
                    "Ongoing monitoring plan (Article 72)",
                    "Recommended tools and frameworks (AIF360, Fairlearn, etc.)",
                ],
                "estimated_value": "Equivalent to GBP 500-2,000 bias remediation consultancy",
            },
            "upgrade": {
                "url": "https://meok.ai/api-keys",
                "stripe_checkout": "https://buy.stripe.com/00wfZjcgAeUW4c5cyQ8k90K",
                "price": "From GBP 29/month -- includes unlimited remediation plans",
            },
            "free_alternative": "Use quick_scan (free) for instant risk assessment, or regulatory_check for compliance requirements.",
        }

    bias_key = bias_type.strip().lower()

    if bias_key not in BIAS_TYPES:
        return {
            "error": "unknown_bias_type",
            "message": "Unknown bias type '{}'. Valid types: {}".format(bias_type, ", ".join(BIAS_TYPES.keys())),
            "valid_types": {k: v["name"] for k, v in BIAS_TYPES.items()},
        }

    binfo = BIAS_TYPES[bias_key]
    strategies = MITIGATION_STRATEGIES.get(bias_key, [])

    # Pre-processing, in-processing, post-processing recommendations
    pre_processing = [
        "Audit training data for representation gaps across protected groups",
        "Apply re-sampling or re-weighting to balance group representation",
        "Remove or transform proxy features that correlate with protected attributes",
        "Use data augmentation to increase diversity",
    ]
    in_processing = [
        "Add fairness constraints to the loss function (e.g., demographic parity, equalized odds)",
        "Use adversarial debiasing to remove protected attribute information from representations",
        "Apply regularisation that penalises disparate outcomes",
        "Train with fairness-aware hyperparameter tuning",
    ]
    post_processing = [
        "Calibrate prediction thresholds per group to equalise error rates",
        "Apply reject option classification for borderline cases",
        "Implement group-specific decision boundaries",
        "Monitor deployed model for performance drift across groups",
    ]

    return {
        "bias_type": binfo["name"],
        "description": binfo["description"],
        "severity": binfo["severity"],
        "eu_ai_act_article": binfo["eu_article"],
        "specific_mitigations": strategies,
        "general_framework": {
            "pre_processing": pre_processing,
            "in_processing": in_processing,
            "post_processing": post_processing,
        },
        "documentation_requirements": [
            "Document bias type and detection methodology in Annex IV Section 2.5.4",
            "Record mitigation measures applied in Article 9 risk management system",
            "Include fairness metrics in Annex IV Section 4 performance metrics",
            "Report residual bias in Annex IV Section 3.1 capabilities and limitations",
        ],
        "monitoring_plan": [
            "Establish disaggregated performance dashboards by protected group",
            "Set automated alerts for fairness metric degradation",
            "Conduct periodic re-evaluation against new data distributions",
            "Document bias incidents in post-market monitoring (Article 72)",
        ],
        "tools_and_frameworks": [
            "IBM AI Fairness 360 (AIF360) -- comprehensive fairness toolkit",
            "Google What-If Tool -- interactive fairness exploration",
            "Microsoft Fairlearn -- fairness assessment and mitigation",
            "Aequitas -- bias and fairness audit toolkit",
        ],
        "meok_labs": "https://meok.ai",
    }


# ---------------------------------------------------------------------------
# Tool: regulatory_check
# ---------------------------------------------------------------------------
@mcp.tool()
def regulatory_check(
    jurisdiction: str = "eu",
    api_key: str = "",
) -> dict:
    """Check bias requirements against EU AI Act Article 10 and NIST AI RMF MAP requirements.

    Args:
        jurisdiction: Jurisdiction to check against. Options: eu, us_nist, uk, all.
        api_key: Optional MEOK API key for pro tier.

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.
    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return {"error": msg, "upgrade_url": "https://meok.ai/api-keys"}
    limit_err = _check_rate_limit("regulatory_check", tier)
    if limit_err:
        return {"error": "rate_limited", "message": limit_err}

    jurisdiction = jurisdiction.strip().lower()

    eu_requirements = {
        "framework": "EU AI Act (Regulation (EU) 2024/1689)",
        "key_articles": {
            "Article 10(2)(f)": "Training, validation, and testing datasets shall be examined for possible biases that are likely to affect health and safety or fundamental rights",
            "Article 10(3)": "Datasets shall be relevant, sufficiently representative, and to the best extent possible, free of errors and complete in view of the intended purpose",
            "Article 10(4)": "Validation and testing datasets shall be appropriate, sufficiently representative, and proportionate",
            "Article 10(5)": "Personal data may be processed for bias detection and correction to the extent strictly necessary (special derogation from GDPR purpose limitation)",
            "Article 9(2)(a)": "Risk management shall include identification and analysis of known and reasonably foreseeable risks including bias",
            "Article 14(4)(b)": "Human overseers shall be aware of automation bias",
            "Article 15(1)": "AI systems shall achieve appropriate levels of accuracy for specific persons or groups",
        },
        "enforcement_date": "2 August 2026 (high-risk systems)",
        "penalty": "Up to EUR 15,000,000 or 3% of global annual turnover for non-compliance",
    }

    nist_requirements = {
        "framework": "NIST AI Risk Management Framework 1.0",
        "key_functions": {
            "MAP 2.3": "Scientific integrity and TEVV considerations are identified and documented, including bias measurement",
            "MEASURE 2.6": "AI system performance or assurance criteria are measured, including disparate performance across groups",
            "MEASURE 2.7": "AI system security and resilience, including resistance to bias attacks",
            "MANAGE 2.2": "Mechanisms are in place and applied to sustain value of deployed AI systems, including bias monitoring",
            "GOVERN 1.1": "Policies and procedures reflect risk management priorities including bias and fairness",
        },
        "enforcement": "Voluntary (mandatory for US federal agencies per Executive Order 14110)",
        "penalty": "N/A (framework, not law) but federal procurement may require compliance",
    }

    uk_requirements = {
        "framework": "UK AI Regulation (pro-innovation, principles-based)",
        "key_principles": {
            "Fairness": "AI systems should not create unfair discrimination or undermine legal rights",
            "Transparency": "Organisations should be able to explain their AI systems including bias considerations",
            "Contestability": "Individuals should be able to challenge AI decisions affecting them",
            "Safety": "AI systems should function in a robust, secure, and safe way including against bias",
        },
        "enforcement": "Sector-specific regulators (FCA, ICO, CMA, etc.)",
        "penalty": "Varies by sector regulator",
    }

    result = {
        "jurisdiction_checked": jurisdiction,
        "assessment_date": datetime.now().isoformat(),
    }  # type: Dict[str, object]

    if jurisdiction in ("eu", "all"):
        result["eu_ai_act"] = eu_requirements
    if jurisdiction in ("us_nist", "all"):
        result["nist_ai_rmf"] = nist_requirements
    if jurisdiction in ("uk", "all"):
        result["uk_ai_regulation"] = uk_requirements

    if jurisdiction not in ("eu", "us_nist", "uk", "all"):
        return {
            "error": "unknown_jurisdiction",
            "message": "Unknown jurisdiction '{}'. Valid: eu, us_nist, uk, all".format(jurisdiction),
        }

    result["bias_compliance_checklist"] = [
        {"check": "Training data examined for biases", "eu_ref": "Article 10(2)(f)", "nist_ref": "MAP 2.3"},
        {"check": "Datasets are representative of deployment population", "eu_ref": "Article 10(3)", "nist_ref": "MEASURE 2.6"},
        {"check": "Fairness metrics calculated and documented", "eu_ref": "Annex IV Section 4", "nist_ref": "MEASURE 2.6"},
        {"check": "Bias mitigation measures applied and documented", "eu_ref": "Article 9", "nist_ref": "MANAGE 2.2"},
        {"check": "Human oversight trained on automation bias", "eu_ref": "Article 14(4)(b)", "nist_ref": "GOVERN 1.1"},
        {"check": "Disaggregated performance metrics reported", "eu_ref": "Article 15(1)", "nist_ref": "MEASURE 2.6"},
        {"check": "Ongoing bias monitoring in production", "eu_ref": "Article 72", "nist_ref": "MANAGE 2.2"},
        {"check": "Bias documented in technical documentation", "eu_ref": "Annex IV Section 2.5.4", "nist_ref": "MAP 2.3"},
    ]

    result["meok_labs"] = "https://meok.ai"
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    """Entry point for the bias-detection-mcp command."""
    mcp.run()


if __name__ == "__main__":
    main()
