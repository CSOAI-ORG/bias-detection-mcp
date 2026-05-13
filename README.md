<div align="center">

# Bias Detection MCP

**MCP server for bias detection mcp operations**

[![PyPI](https://img.shields.io/pypi/v/meok-bias-detection-mcp)](https://pypi.org/project/meok-bias-detection-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MEOK AI Labs](https://img.shields.io/badge/MEOK_AI_Labs-MCP_Server-purple)](https://meok.ai)

</div>


## Quick Install

| Client | Install |
|--------|---------|
| **Claude Desktop** | [![Install in Claude](https://img.shields.io/badge/Install-Claude-blue)](https://claude.ai) |
| **Cursor** | [![Install in Cursor](https://img.shields.io/badge/Install-Cursor-black)](https://cursor.com) |
| **VS Code** | [![Install in VS Code](https://img.shields.io/badge/Install-VS_Code-blue)](https://code.visualstudio.com) |
| **Windsurf** | [![Install in Windsurf](https://img.shields.io/badge/Install-Windsurf-purple)](https://codeium.com/windsurf) |
| **Docker** | `docker run -p 8000:8000 bias-detection-mcp` |
| **pip** | `pip install bias-detection-mcp` |

## Overview

Bias Detection MCP provides AI-powered tools via the Model Context Protocol (MCP).

## Tools

| Tool | Description |
|------|-------------|
| `quick_scan` | Describe an AI system in one sentence -> instant bias risk assessment. No API ke |
| `detect_bias` | Analyze text for demographic bias patterns, stereotyping, and unfair language. |
| `fairness_metrics` | Calculate fairness metrics from prediction data. Input format: comma-separated v |
| `mitigation_recommendations` | Get detailed remediation steps for a specific type of AI bias. |
| `regulatory_check` | Check bias requirements against EU AI Act Article 10 and NIST AI RMF MAP require |

## Installation

```bash
pip install meok-bias-detection-mcp
```

## Usage with Claude Desktop

Add to your Claude Desktop MCP config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "bias-detection-mcp": {
      "command": "python",
      "args": ["-m", "meok_bias_detection_mcp.server"]
    }
  }
}
```

## Usage with FastMCP

```python
from mcp.server.fastmcp import FastMCP

# This server exposes 5 tool(s) via MCP
# See server.py for full implementation
```

> **If this tool helps your compliance workflow, please [star this repo](https://github.com/meok-ai-labs/bias-detection-mcp/stargazers)** — it helps other teams find it.

## License

MIT © [MEOK AI Labs](https://meok.ai)

<!-- mcp-name: io.github.CSOAI-ORG/bias-detection-mcp -->
