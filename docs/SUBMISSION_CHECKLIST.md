# Submission Checklist — 18 Rules

> Walks every hackathon rule. Ticked by `P6-ALL-05`. This file is the
> authoritative gate; nothing ships until every box is ✅.

| # | Rule | How satisfied | Ticked |
|---|---|---|---|
| 1 | Solo or team of up to 4; one team per person | `docs/TEAM.md` declares solo entry | ☐ |
| 2 | FalkorDB is the primary graph DB and central | All data, memory, tasks, vectors in FalkorDB per `docs/SCHEMA.md` | ☐ |
| 3 | Graph does real work, not decoration | `evals/baseline_vector_only.py` shows failures without graph; documented in README | ☐ |
| 4 | Any way to run FalkorDB | Docker Compose + FalkorDB Cloud option in `docker-compose.yml` / README | ☐ |
| 5 | Name every track on submit | README header + portal form name all 3 tracks | ☐ |
| 6 | Only public, synthetic or own data | `data/generate_synthetic.py` with fixed seed; emails `example.com` | ☐ |
| 7 | Window 15 Oct 00:01 to 18 Oct 23:59 IST | Internal deadline Sun 20:00 | ☐ |
| 8 | Main coding starts after the start | Repo created inside the window; only planning docs pre-window | ☐ |
| 9 | Libraries, APIs, templates allowed; original work judged | `THIRD_PARTY.md` lists everything | ☐ |
| 10 | Public repo, README, Cypher doc, video, deploy, track | All linked from README | ☐ |
| 11 | Disclose AI coding assistants | `docs/AI_DISCLOSURE.md` + PR template field | ☐ |
| 12 | Explain model, queries, architecture, decisions | `P6-ALL-02` drill; `docs/CONTRIBUTIONS.md` | ☐ |
| 13 | Not entirely AI-generated; meaningful contribution | Each query hand-tested in Browser; tests in `tests/` | ☐ |
| 14 | Prizes per track | Demo script has one beat per track (`docs/demo_script.md`) | ☐ |
| 15 | IP belongs to team; agree internally | `docs/TEAM.md` + `LICENSE` (MIT) | ☐ |
| 16 | Conduct | Code of conduct statement | ☐ |
| 17 | No plagiarism | `THIRD_PARTY.md`; all original code | ☐ |
| 18 | No judging manipulation | Public repo only, no closed assets | ☐ |