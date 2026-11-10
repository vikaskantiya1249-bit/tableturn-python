# TableTurn (Python)

[![tests](https://github.com/vikaskantiya1249-bit/tableturn-python/actions/workflows/tests.yml/badge.svg)](https://github.com/vikaskantiya1249-bit/tableturn-python/actions/workflows/tests.yml)

A restaurant waitlist: parties quoted a wait, seated by size, tables turning over all evening.

## Progress

- [x] Ticket 1 · The floor, as something you can look at
- [x] Ticket 2 · A party joins the list
- [x] Ticket 3 · The wait you quote, and the wait they actually have
- [x] Ticket 4 · Three ways to say no
- [x] Ticket 5 · The table turns
- [ ] Ticket 6 · A board nobody can wipe
- [ ] Ticket 7 · One file becomes an app
- [ ] Ticket 8 · The rule table, and then the rule changes
- [ ] Ticket 9 · It runs on the machine by the till
- [ ] Ticket 10 · It survives the nightly power cut

## Run it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest          # the tests
python -m uvicorn tableturn.app:app --port 8080   # the app, on http://127.0.0.1:8080
```

## Built with

Python 3.12 · FastAPI · SQLAlchemy · Pydantic · pytest

---

Built by Vikas on [LearnTube Guided Projects](https://guidedprojects.learntube.ai).
