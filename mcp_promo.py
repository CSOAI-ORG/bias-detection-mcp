"""MEOK MCP — First-run onboarding prompt."""
import os, json, sys

_ONBOARD_FILE = os.path.expanduser("~/.meok_onboarded")

def _show_onboarding():
    if os.path.exists(_ONBOARD_FILE):
        return
    
    print("\n" + "="*60)
    print("🔐 MEOK AI — Enterprise Compliance Tools via MCP")
    print("="*60)
    print("You just installed a MEOK MCP server.")
    print("Free tier: 100 calls/day | Pro: $99/mo | Enterprise: $499/mo")
    print("")
    print("👉 Dashboard: https://meok-saas.vercel.app/dashboard")
    print("👉 Get API key: https://meok-saas.vercel.app/signup")
    print("👉 Docs: https://meok.ai/docs")
    print("="*60 + "\n")
    
    try:
        os.makedirs(os.path.dirname(_ONBOARD_FILE), exist_ok=True)
        with open(_ONBOARD_FILE, "w") as f:
            json.dump({"onboarded": True, "timestamp": __import__("time").strftime("%Y-%m-%d")}, f)
    except:
        pass

_show_onboarding()
