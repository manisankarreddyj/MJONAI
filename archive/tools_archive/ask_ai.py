import os
import json
import requests

def ask_ollama(question, project_path="/mnt/d/mjonai_build"):
    """Ask Ollama a question about your project."""
    
    # Read key files for context
    context_parts = []
    key_files = [
        "core/constants.py",
        "research/grid_tester_v2.py",
        "research/cost_model.py",
        "MJONAI_AGENT_PLAN.md",
    ]
    
    for f in key_files:
        full_path = os.path.join(project_path, f)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r') as fh:
                    content = fh.read()[:2000]  # First 2000 chars
                context_parts.append(f"\n--- {f} ---\n{content}")
            except:
                pass
    
    context = "\n".join(context_parts)
    
    prompt = f"""You are helping with a trading system called MJONAI.

PROJECT FILES:
{context[:5000]}

USER QUESTION: {question}

Answer based on the project files above."""
    
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1",
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )
    
    return response.json()["response"]

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Ask: ")
    
    answer = ask_ollama(question)
    print(f"\n{answer}")
