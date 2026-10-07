# Unified LLM client.
import os, json, requests

class LLM:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY", "")
        self.base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = os.environ.get("LLM_MODEL", "gpt-4o")

    def chat(self, messages, temperature=0.7, max_tokens=2048):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        r = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def classify(self, text, categories, instructions=""):
        sep = ", "
        prompt = f"{instructions}Classify: {text}
Categories: {sep.join(categories)}
Respond as JSON: {{"category": "...", "confidence": 0.95, "reasoning": "..."}}"
        raw = self.chat([{"role": "system", "content": "Respond only with valid JSON."}, {"role": "user", "content": prompt}])
        start, end = raw.find("{"), raw.rfind("}") + 1
        try:
            return json.loads(raw[start:end])
        except:
            return {"category": "unknown", "confidence": 0.0, "reasoning": raw}

    def generate(self, prompt, system="You are a helpful AI assistant.", temperature=0.7):
        return self.chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], temperature=temperature)
