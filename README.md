# BrandForge

**Startup name forge** — generate brandable names at scale, filter for length and pronunciation, check `.com` + GitHub availability, prepare trademark research dossiers, and export logo kits.

Built for founders who need a name they can keep for years — not a throwaway project label.

```
Word Generator
      │
      ▼
 ~100,000 Names
      │
      ▼
 Length Filter (5–10)
      │
      ▼
 Pronunciation Filter
      │
      ▼
 .com Checker (RDAP)
      │
      ▼
 GitHub Checker
      │
      ▼
 Trademark Report
      │
      ▼
 Top 10–20 + Logos
```

---

## Features

- **Mass generation** — prefix × suffix blends (`Mer` + `ixa` → *Merixa*) plus phonetic syllables to reach ~100k candidates
- **Quality filters** — length (5–10) and pronounceability heuristics
- **Domain check** — live `.com` availability via Verisign RDAP
- **GitHub check** — username / org availability via GitHub API
- **Trademark dossier** — USPTO / EUIPO / WIPO research links + heuristic risk (not legal advice)
- **Category mode** — AI, e-commerce, healthcare, finance, cybersecurity, education, cloud
- **Logo kits** — SVG wordmark, PNG export, and a reusable AI logo prompt per winner

---

## Quick start

```bash
git clone https://github.com/BartuDonmez0/BrandForge.git
cd BrandForge
pip install -r requirements.txt
python generate.py
```

Optional (higher GitHub API limits):

```bash
cp .env.example .env
# set BRANDFORGE_GITHUB_TOKEN=ghp_...
```

---

## Usage

```bash
# Full pipeline
python generate.py
python generate.py --category ai --top 20 --max-check 400

# Categories
python generate.py --category ecommerce
python generate.py --category healthcare
python generate.py --category finance
python generate.py --category cybersecurity
python generate.py --category education
python generate.py --category cloud
python generate.py categories

# Probe one name
python generate.py check Lumivo

# Logo kit only
python generate.py logo Merixa --category ai
```

### Useful flags

| Flag | Meaning |
|------|---------|
| `--count / -n` | Pool size (default `100000`) |
| `--top / -t` | Winners to keep (default `20`) |
| `--max-check` | How many names to probe online |
| `--category / -c` | Tuned roots for a niche |
| `--no-domain` | Skip `.com` checks |
| `--no-github` | Skip GitHub checks |
| `--no-logo` | Skip logo generation |
| `--seed` | Reproducible runs |

---

## Outputs

| Path | Contents |
|------|----------|
| `output/reports/*.md` | Ranked brand dossier |
| `output/reports/*.json` | Machine-readable results |
| `output/logos/<name>.svg` | Lettermark SVG |
| `output/logos/<name>.png` | Wordmark PNG |
| `output/logos/<name>.prompt.txt` | Logo prompt for image models |

---

## How names are built

Roots and endings combine into coined brands:

| Prefix | Suffix | Result |
|--------|--------|--------|
| mer | ixa | **Merixa** |
| lum | ivo | **Lumivo** |
| syn | ora | **Synora** |
| vel | ixa | **Velixa** |

Category mode swaps in niche vocabulary (e.g. AI → `cogn`, `neur`, `tensor` …).

---

## Project layout

```
BrandForge/
├── generate.py              # CLI entrypoint
├── brandforge/
│   ├── generators/          # Name pool
│   ├── filters/             # Length + pronunciation
│   ├── checkers/            # Domain, GitHub, trademark
│   ├── logo/                # SVG / PNG / prompts
│   ├── pipeline.py          # End-to-end flow
│   └── cli.py               # Typer + Rich UI
├── output/                  # Reports & logos (gitignored)
└── requirements.txt
```

---

## Trademark note

USPTO / EUIPO scores are **heuristics** with deep links for manual review. They are **not legal advice**. Always verify before filing or launching.

---

## Roadmap

- [ ] LLM-assisted naming for a given product brief
- [ ] Multi-TLD checks (`.io`, `.ai`, `.co`)
- [ ] Social handle availability (X, Instagram, …)
- [ ] Full brand kit export (colors, typography, one-pager)
- [ ] Hosted SaaS layer on top of this CLI core

---

## License

MIT © [Bartu Dönmez](https://github.com/BartuDonmez0)
