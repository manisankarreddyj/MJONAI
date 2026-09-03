import os, json, requests, sys

def ask(question):
    """Ask Ollama about your MJONAI project."""
    
    # Read only the most important file for context
    context = ""
    try:
        with open("MJONAI_AGENT_PLAN.md", "r") as f:
            context = f.read()[:1500]  # First 1500 chars only
    except:
        context = "MJONAI is a stock trading system."
    
    prompt = f"""You are the CEO agent for MJONAI, a stock trading system.

PLAN SUMMARY:
{context}

USER QUESTION: {question}

Be concise. Answer in 5 sentences max."""
    
    r = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "llama3.1", "prompt": prompt, "stream": False},
        timeout=60
    )
    return r.json()["response"]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    else:
        q = input("Ask: ")
    print(ask(q))
