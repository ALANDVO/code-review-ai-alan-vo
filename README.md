# code-review-ai-alan-vo

> AI code review assistant that analyzes diffs or files for bugs, security issues, style problems, and performance pitfalls, generating line-by-line review comments for Python, JS, Go, and Rust.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-React-3178C6)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)
![SSO](https://img.shields.io/badge/SSO-SAML%20%2F%20OAuth2-8A2BE2)
![License](https://img.shields.io/badge/License-MIT-green)
![AI](https://img.shields.io/badge/AI-Powered-purple)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

</div>

## Why code-review-ai-alan-vo?

AI code review assistant that analyzes diffs or files for bugs, security issues, style problems, and performance pitfalls, generating line-by-line review comments for Python, JS, Go, and Rust.

Built by [Alan Vo](https://github.com/ALANDVO) — AI/ML & cybersecurity engineer.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     code-review-ai-alan-vo                                    │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│  Frontend   │   API Layer │  Services   │   LLM Engine      │
│  React/TS   │  FastAPI    │  Domain     │  Multi-provider   │
│  Dashboard  │  SSO/SAML   │  Logic      │  OpenAI/Claude/   │
│  Real-time  │  JWT Auth   │  Processing │  Gemini/Ollama    │
└─────────────┴─────────────┴─────────────┴───────────────────┘
         │              │              │               │
         ▼              ▼              ▼               ▼
    ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────────┐
    │ Browser │   │  REST   │   │  Domain │   │  LLM API    │
    │  SPA    │   │  API    │   │  Logic  │   │  (any)      │
    └─────────┘   └─────────┘   └─────────┘   └─────────────┘
```

## Features

- **Diff-based review: paste a unified diff and get line-by-line comments**
- **Full-file review with function-level analysis and cross-reference**
- **Security scanning: injection, secrets, auth flaws, unsafe deserialization**
- **Performance detection: O(n²) patterns, needless allocations, N+1 queries**
- **Style and maintainability feedback with severity levels**
- **Multi-language: Python, JavaScript/TypeScript, Go, Rust**
- **Export reviews to JSON, Markdown, or PR-comment-ready format**

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/ALANDVO/code-review-ai-alan-vo.git
cd code-review-ai-alan-vo
cp .env.example .env
docker compose up -d
# Open http://localhost:3000
```

### Local Development

```bash
git clone https://github.com/ALANDVO/code-review-ai-alan-vo.git
cd code-review-ai-alan-vo
pip install -r requirements.txt
```

## Usage

```
python main.py review --file src/auth.py --lang python
python main.py diff --file changes.diff --lang javascript
python main.py review --file main.go --lang go --focus security,performance
python main.py review --stdin --lang rust < code.rs
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | LLM API key (OpenAI, Anthropic, Gemini) | Required |
| `LLM_BASE_URL` | Custom LLM endpoint (Ollama, vLLM) | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model name | `gpt-4o` |
| `SAML_IDP_ENTITY` | SAML Identity Provider URL | — |
| `JWT_SECRET` | JWT signing secret | Generate one |

## Tech Stack

`Python` `OpenAI/Anthropic/Gemini` `Code Review` `Static Analysis` `Security` `Python/JS/Go/Rust`

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Login (SSO or email) |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/stats` | Statistics & metrics |
| `POST` | `/api/process` | Main processing endpoint |
| `GET` | `/api/results` | Query results |

## SSO Setup

### SAML
1. Set `SAML_IDP_ENTITY` to your IdP URL
2. Set `SAML_IDP_CERT` to your IdP certificate
3. Set `SAML_ACS_URL` to `https://yourdomain.com/saml/acs`

### OAuth2
1. Register your app with the OAuth provider
2. Set `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET`
3. Set `OAUTH_REDIRECT_URI`

## License

MIT — see [LICENSE](LICENSE)

---

**Built by [Alan Vo](https://github.com/ALANDVO)** | alanvo@gmail.com | AI, ML & Cybersecurity


