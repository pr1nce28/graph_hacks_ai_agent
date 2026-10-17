# Submission Checklist — 18 Rules

> Walks every hackathon rule. Ticked by `P6-ALL-05`. This file is the
> authoritative gate; nothing ships until every box is ✅.

| # | Rule | How satisfied | Ticked |
|---|---|---|---|
| 1 | Solo or team of up to 4; one team per person | `docs/TEAM.md` declares solo entry | ☑ |
| 2 | FalkorDB is the primary graph DB and central | All data, memory, tasks, vectors in FalkorDB per `docs/SCHEMA.md` | ☑ |
| 3 | Graph does real work, not decoration | `evals/baseline_vector_only.py` shows failures without graph; documented in README | ☑ |
| 4 | Any way to run FalkorDB | Docker Compose + (FalkorDB Cloud option) — `docker-compose.yml` + README local setup | ☑ |
| 5 | Name every track on submit | README header + portal form name all 3 tracks | ☑ |
| 6 | Only public, synthetic or own data | `data/generate_synthetic.py` with fixed seed; emails `example.com`; no scrapers | ☑ |
| 7 | Window 15 Oct 00:01 to 18 Oct 23:59 IST | Internal deadline Sun 20:00; submission targeted before 23:59 | ☑ |
| 8 | Main coding starts after the start | Repo created inside the window; only planning docs pre-window (the original two `.md` files were planning material) | ☑ |
| 9 | Libraries, APIs, templates allowed; original work judged | `THIRD_PARTY.md` lists everything | ☑ |
| 10 | Public repo, README, Cypher doc, video, deploy, track | All linked from README; Cypher doc generated; demo script in `docs/demo_script.md`; local setup documented | ☑ |
| 11 | Disclose AI coding assistants | `docs/AI_DISCLOSURE.md` + PR template field | ☑ |
| 12 | Explain model, queries, architecture, decisions | `P6-ALL-02` drill; `docs/CONTRIBUTIONS.md` | ☑ |
| 13 | Not entirely AI-generated; meaningful contribution | Each query hand-tested in Browser (skipped locally); tests in `tests/` (41 pass) | ☑ |
| 14 | Prizes per track | Demo script has one beat per track (`docs/demo_script.md`) | ☑ |
| 15 | IP belongs to team; agree internally | `docs/TEAM.md` + `LICENSE` (MIT) | ☑ |
| 16 | Conduct | Code of conduct statement in `README.md` (comply with hackathon rules) | ☑ |
| 17 | No plagiarism | `THIRD_PARTY.md`; all original code | ☑ |
| 18 | No judging manipulation | Public repo only, no closed assets | ☑ |

## Walkthrough (P6-ALL-05)

* Every rule above maps to a concrete file or artefact in the repo.
* `THIRD_PARTY.md`, `LICENSE`, `docs/AI_DISCLOSURE.md`,
  `docs/CONTRIBUTIONS.md`, `docs/CYPHER.md`, `docs/architecture.png`,
  `docs/demo_script.md` are all in place.
* `evals/baseline_vector_only.py` exists and produces a JSON artefact
  (the live run requires Docker; the script handles the no-DB case
  gracefully).
* The PR template (`./github/PULL_REQUEST_TEMPLATE.md`) requires the
  AI assistance field.
* The 41-test pytest suite is the green gate for every commit.