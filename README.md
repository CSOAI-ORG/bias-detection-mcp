# AI Bias Detection MCP Server

By [MEOK AI Labs](https://meok.ai) | The only MCP server for AI bias detection and fairness assessment.

## Quick Start

```bash
pip install bias-detection-mcp
bias-detection-mcp
```

Or run directly:

```bash
pip install mcp
python server.py
```

## Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bias-detection": {
      "command": "bias-detection-mcp"
    }
  }
}
```

## Tools

| Tool | Description | API Key Required |
|------|-------------|-----------------|
| `quick_scan` | Describe an AI system, get instant bias risk assessment | No |
| `detect_bias` | Analyze text for demographic bias patterns | No (free tier) |
| `fairness_metrics` | Calculate disparate impact, equalized odds, statistical parity | No (free tier) |
| `mitigation_recommendations` | Get remediation steps for specific bias types | No (free tier) |
| `regulatory_check` | Check bias compliance against EU AI Act / NIST AI RMF | No (free tier) |

## Free Tier

10 calls/day per tool, no API key required. Upgrade to Pro ($29/mo) for unlimited access at [meok.ai](https://meok.ai/mcp/bias-detection/pro).

## Examples

### Quick Scan (zero config)
```
quick_scan("Hiring screening tool that ranks candidates based on CV keywords and university name")
```

### Detect Bias in Model Output
```
detect_bias("Male candidates are typically more suited for engineering roles", "gender")
```

### Calculate Fairness Metrics
```
fairness_metrics("male:1,male:1,male:0,female:0,female:0,female:1")
```

## License

MIT - Built by [MEOK AI Labs](https://meok.ai)
