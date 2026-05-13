"""
Tests for AI Bias Detection MCP Server
========================================
Tests every @mcp.tool() function directly (no MCP protocol).
Run: cd /Users/nicholas/clawd/mcp-marketplace/bias-detection-mcp && pytest test_server.py -v
"""

import json
import sys
import os

os.environ.pop("MEOK_API_KEY", None)

sys.path.insert(0, os.path.dirname(__file__))

from server import (
    quick_scan,
    detect_bias,
    fairness_metrics,
    mitigation_recommendations,
    regulatory_check,
    _usage,
    BIAS_TYPES,
)


def _reset_rate_limits():
    _usage.clear()


# ── quick_scan ─────────────────────────────────────────────────────

class TestQuickScan:
    def setup_method(self):
        _reset_rate_limits()

    def test_basic_low_risk(self):
        result = quick_scan("A spell check tool for documents")
        assert isinstance(result, dict)
        assert "bias_risk_level" in result
        assert result["bias_risk_level"] in ("low", "moderate", "high")

    def test_high_risk_hiring(self):
        result = quick_scan("AI system for hiring and recruitment screening of candidates")
        assert isinstance(result, dict)
        assert result["bias_risk_level"] == "high"

    def test_high_risk_credit(self):
        result = quick_scan("AI system for credit scoring and loan approval decisions")
        assert isinstance(result, dict)
        assert result["bias_risk_level"] == "high"

    def test_moderate_risk_chatbot(self):
        result = quick_scan("A chatbot for customer service")
        assert isinstance(result, dict)
        assert result["bias_risk_level"] in ("low", "moderate")

    def test_empty_string(self):
        result = quick_scan("")
        assert isinstance(result, dict)
        assert "bias_risk_level" in result
        assert result["bias_risk_level"] == "low"

    def test_returns_score(self):
        result = quick_scan("Facial recognition for biometric identification")
        assert isinstance(result, dict)
        assert "bias_risk_score" in result
        assert isinstance(result["bias_risk_score"], float)
        assert 0.0 <= result["bias_risk_score"] <= 1.0

    def test_returns_actions(self):
        result = quick_scan("AI for insurance pricing based on health data")
        assert isinstance(result, dict)
        assert "top_3_actions" in result
        assert isinstance(result["top_3_actions"], list)
        assert len(result["top_3_actions"]) > 0

    def test_protected_attributes_detected(self):
        result = quick_scan("AI system that uses race and gender data for hiring decisions")
        assert isinstance(result, dict)
        assert "protected_attributes_detected" in result
        attrs = result["protected_attributes_detected"]
        assert isinstance(attrs, list)
        assert len(attrs) > 0

    def test_eu_ai_act_relevance(self):
        result = quick_scan("A tool for weather forecasting")
        assert isinstance(result, dict)
        assert "eu_ai_act_relevance" in result


# ── detect_bias ────────────────────────────────────────────────────

class TestDetectBias:
    def setup_method(self):
        _reset_rate_limits()

    def test_free_tier_returns_preview(self):
        """Free tier should return a pro_feature gate with a preview."""
        result = detect_bias("All women are less qualified for technical roles")
        assert isinstance(result, dict)
        assert result.get("error") == "pro_feature"
        assert "preview" in result
        assert "quick_bias_level" in result["preview"]

    def test_free_tier_preview_high_bias(self):
        result = detect_bias(
            "All elderly people are not capable of using technology. Those people tend to be less qualified."
        )
        assert isinstance(result, dict)
        assert result.get("error") == "pro_feature"
        preview = result["preview"]
        assert preview["quick_bias_level"] in ("HIGH", "MODERATE", "LOW", "MINIMAL")

    def test_free_tier_preview_low_bias(self):
        result = detect_bias("The weather today is sunny with a chance of rain.")
        assert isinstance(result, dict)
        preview = result.get("preview", {})
        assert preview.get("quick_bias_level") in ("LOW", "MINIMAL")

    def test_empty_text(self):
        result = detect_bias("")
        assert isinstance(result, dict)

    def test_with_protected_attributes_param(self):
        result = detect_bias(
            "This candidate was not selected",
            protected_attributes="race,gender",
        )
        assert isinstance(result, dict)

    def test_upgrade_url_present(self):
        result = detect_bias("Some text about hiring decisions")
        assert isinstance(result, dict)
        if "upgrade" in result:
            assert "url" in result["upgrade"]


# ── fairness_metrics ───────────────────────────────────────────────

class TestFairnessMetrics:
    def setup_method(self):
        _reset_rate_limits()

    def test_free_tier_gate(self):
        result = fairness_metrics("male:1,female:0,male:1,female:1")
        assert isinstance(result, dict)
        assert result.get("error") == "pro_feature"

    def test_free_tier_groups_detected(self):
        result = fairness_metrics("male:1,female:0,male:1,female:1,male:0,female:0")
        assert isinstance(result, dict)
        preview = result.get("preview", {})
        groups = preview.get("groups_detected", [])
        assert "male" in groups
        assert "female" in groups

    def test_empty_predictions(self):
        result = fairness_metrics("")
        assert isinstance(result, dict)

    def test_single_group(self):
        result = fairness_metrics("male:1,male:0,male:1")
        assert isinstance(result, dict)

    def test_with_ground_truth(self):
        result = fairness_metrics(
            "male:1,female:0,male:1,female:1",
            ground_truth="male:1,female:1,male:0,female:1",
        )
        assert isinstance(result, dict)


# ── mitigation_recommendations ─────────────────────────────────────

class TestMitigationRecommendations:
    def setup_method(self):
        _reset_rate_limits()

    def test_free_tier_gate(self):
        result = mitigation_recommendations("selection")
        assert isinstance(result, dict)
        assert result.get("error") == "pro_feature"

    def test_valid_bias_type_preview(self):
        result = mitigation_recommendations("selection")
        assert isinstance(result, dict)
        preview = result.get("preview", {})
        assert preview.get("bias_type_valid") is True

    def test_invalid_bias_type(self):
        result = mitigation_recommendations("nonexistent_bias")
        assert isinstance(result, dict)
        preview = result.get("preview", {})
        assert preview.get("bias_type_valid") is False

    def test_all_bias_types_accepted(self):
        """Ensure every known bias type is accepted in the preview."""
        for bias_type in BIAS_TYPES:
            _reset_rate_limits()
            result = mitigation_recommendations(bias_type)
            assert isinstance(result, dict)
            preview = result.get("preview", {})
            assert preview.get("bias_type_valid") is True, f"Failed for bias type: {bias_type}"

    def test_empty_string(self):
        result = mitigation_recommendations("")
        assert isinstance(result, dict)

    def test_case_insensitive(self):
        _reset_rate_limits()
        result = mitigation_recommendations("SELECTION")
        assert isinstance(result, dict)
        preview = result.get("preview", {})
        assert preview.get("bias_type_valid") is True


# ── regulatory_check ───────────────────────────────────────────────

class TestRegulatoryCheck:
    def setup_method(self):
        _reset_rate_limits()

    def test_eu_jurisdiction(self):
        result = regulatory_check(jurisdiction="eu")
        assert isinstance(result, dict)
        assert "eu_ai_act" in result

    def test_us_nist_jurisdiction(self):
        result = regulatory_check(jurisdiction="us_nist")
        assert isinstance(result, dict)
        assert "nist_ai_rmf" in result

    def test_uk_jurisdiction(self):
        result = regulatory_check(jurisdiction="uk")
        assert isinstance(result, dict)
        assert "uk_ai_regulation" in result

    def test_all_jurisdictions(self):
        result = regulatory_check(jurisdiction="all")
        assert isinstance(result, dict)
        assert "eu_ai_act" in result
        assert "nist_ai_rmf" in result
        assert "uk_ai_regulation" in result

    def test_invalid_jurisdiction(self):
        result = regulatory_check(jurisdiction="mars")
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] == "unknown_jurisdiction"

    def test_default_jurisdiction_is_eu(self):
        result = regulatory_check()
        assert isinstance(result, dict)
        assert "eu_ai_act" in result

    def test_compliance_checklist_present(self):
        result = regulatory_check(jurisdiction="eu")
        assert isinstance(result, dict)
        assert "bias_compliance_checklist" in result
        assert isinstance(result["bias_compliance_checklist"], list)
        assert len(result["bias_compliance_checklist"]) > 0

    def test_empty_string_jurisdiction(self):
        result = regulatory_check(jurisdiction="")
        assert isinstance(result, dict)
        # Empty string is not a valid jurisdiction
        assert "error" in result


# ── Rate Limiting ──────────────────────────────────────────────────

class TestRateLimiting:
    def setup_method(self):
        _reset_rate_limits()

    def test_quick_scan_rate_limit_after_10(self):
        for i in range(10):
            result = quick_scan(f"Test system {i}")
            assert result.get("error") != "rate_limited", f"Rate limited too early at call {i+1}"

        result = quick_scan("Eleventh call")
        assert isinstance(result, dict)
        if "error" in result:
            assert result["error"] == "rate_limited"
