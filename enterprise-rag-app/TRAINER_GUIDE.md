# Trainer Guide: Running This as a Training Session

This is written for **you, the person running the session** — not the
person learning. It assumes you're teaching one person (or a small group)
who has moderate computer comfort but no RAG/vector-database/React
background, using `ONE_DAY_PLAN.md` as the hands-on material she'll follow.
This guide is the layer above that: how to prepare, how to open, how to
pace and narrate each block, and what to do when something breaks live.

**Vector database for this session: Elasticsearch**, with Chroma kept as a
one-line fallback (`VECTOR_DB_BACKEND=chroma` in `.env`) if the Elasticsearch
install eats too much time. Don't treat that fallback as failure — treat it
as the plan working as designed.

---

## Part 1 — Before the session

### One week before (if you can)

Do a **full dry run yourself**, ideally on hardware similar to hers (same
OS version, similar RAM). This is the single highest-leverage thing you can
do — you want to hit the Elasticsearch heap-size issue, the PowerShell
execution-policy prompt, and the CORS gotcha *before* she does, not during.
Time yourself; if it takes you longer than the hours budgeted in
`ONE_DAY_PLAN.md`, plan to cut the optional exercises in Hour 6 rather than
rushing the fundamentals in Hours 1-4.

### The night before

- Confirm your **OpenAI API key** works: a quick `curl` or the `/docs` page
  against a throwaway ingest + chat call. Nothing derails a session faster
  than debugging an invalid key live.
- Confirm the laptop meets Elasticsearch's practical minimum: **8GB RAM**
  comfortably, less than that and you should default straight to Chroma and
  skip the Elasticsearch portion entirely rather than fight it live.
- Pre-download the Elasticsearch Windows ZIP yourself if you have any
  control over the machine beforehand — it's a large download, and doing it
  live burns 10-15 minutes of session time on a slow connection.
- Print or have on a second screen: this guide, `ONE_DAY_PLAN.md`, and the
  cheat-sheet artefact (see [Part 4](#part-4--artefacts-checklist)).

### Materials checklist

- [ ] This repo cloned/copied onto her machine
- [ ] Your OpenAI API key, tested, written down somewhere you can paste from (not read aloud character by character)
- [ ] Elasticsearch Windows ZIP downloaded ahead of time if possible
- [ ] `ONE_DAY_PLAN.md` open or printed — this is what she'll follow hands-on
- [ ] The cheat-sheet artefact open on a second screen/phone
- [ ] A notepad or shared doc to jot down anything that goes wrong, for your own notes afterward

---

## Part 2 — How to open the session (first 15 minutes)

**Don't start with `setup.ps1`.** Start by showing her the destination, not
the map. Open the finished app yourself (on your own machine, or a
screen-shared demo) and let her ask you 3-4 questions in the chat UI before
either of you writes a single command. The goal of these 15 minutes is that
she can answer "why would anyone want this?" in her own words before
touching a keyboard.

A script you can adapt:

> "This is a chatbot that only answers from documents we give it — it won't
> make things up, and it'll show you exactly which document it got each
> answer from. Companies use this so employees can ask questions instead of
> hunting through PDFs. By the end of today, you'll have built this exact
> thing yourself, running on your own laptop, and you'll understand every
> piece of it well enough to explain it to someone else."

Then set expectations for the day: it's hands-on, she drives the keyboard
as much as possible, mistakes and error messages are expected and are part
of the material — not a sign something's going wrong.

---

## Part 3 — How to conduct each block

`ONE_DAY_PLAN.md` has the hour-by-hour structure and exact commands. Your
job in each block is different from what's written there — it's written
*to* her; this section is written *to you* about how to run it.

### General facilitation rules for the whole day

1. **She types, you narrate.** Resist doing it for her, even when it would
   be faster. Typing the command herself is what makes it stick.
2. **Ask her to predict before running.** Before `POST /ingest`, ask "what
   do you think this is about to do?" Before a chat question, ask "what do
   you expect the sources will be?" Being wrong and finding out why is
   more memorable than being told.
3. **Narrate errors as data, not failure.** If PowerShell blocks a script
   or a port's already in use, say "good, now we get to see what this
   error actually means" rather than rushing to fix it for her.
4. **Checkpoint out loud.** Each hour in `ONE_DAY_PLAN.md` has a
   **Checkpoint**. Don't silently confirm it yourself — ask her to explain
   what she's looking at and why it means that step worked.

### Hour 1 (concepts) — conduct this as a conversation, not a lecture

Use the analogy in `HOW_RAG_WORKS.md` (open-book exam) and stop after every
concept to ask her to restate it. If she can't restate "why do we chunk
documents instead of sending the whole file," stay here — everything after
this hour is easier to teach if this lands first, and harder to teach if it
doesn't.

### Hour 2-3 (backend + Elasticsearch) — this is where the day is most at risk

This is the one block most likely to eat your buffer time, because it's the
only part of the day that involves installing and running a real database
server rather than a Python/npm dependency. Follow
`backend/README_ELASTICSEARCH.md` for the exact steps. Facilitation notes:

- Start the Elasticsearch download **before** Hour 1 begins if you didn't
  pre-download it — kick it off, then go do Hour 1 while it downloads in
  the background.
- When you disable security in `elasticsearch.yml`, explain *why* in one
  sentence ("this is only OK because it never leaves this laptop") rather
  than skipping past it — it's a real security concept worth 30 seconds.
- **Set a hard time box.** If Elasticsearch isn't answering on
  `localhost:9200` within 20 minutes of starting it, stop, switch
  `VECTOR_DB_BACKEND` to `chroma` in `.env`, and move on. Come back to
  Elasticsearch at the end of the day if time allows — don't let it
  consume Hours 4-7.
- Once `/ingest` succeeds, have her open `http://localhost:9200/rag_documents/_count`
  directly in a browser. Seeing the raw Elasticsearch response (not just
  the app's `/health` endpoint) is what makes "this is a real database"
  concrete instead of abstract.

### Hour 4 (frontend) — the payoff moment

This is usually the most satisfying hour because the UI suddenly exists.
Let her sit with it for a minute before moving on — ask her to try breaking
it (ask something unrelated to the documents, ask something ambiguous)
before you move to the code walkthrough.

### Hour 5 (code walkthrough) — pace to her, not to the list

The six files listed in `ONE_DAY_PLAN.md` are a ceiling, not a requirement.
If she's engaged and asking questions about `pipeline.py`, stay there
longer and cut from Hour 6 later rather than rushing to file six.

### Hour 6 (make it hers) — protect this even if you're behind

If time is tight, this is the block to shorten, not cut. Even one
customization (swapping in her own sample document, or renaming the header)
matters more for retention than finishing every code file in Hour 5.

### Hour 7 (restart-and-verify) — don't skip this even if you're out of time

This is the actual test of whether the day succeeded: can she close
everything, reopen it days from now with nobody helping, and have it work?
If you have to cut something, cut Hour 6's exercises before you cut this.

---

## Part 4 — Artefacts checklist

Everything referenced in this guide, in one place:

| Artefact | Where | Purpose |
| --- | --- | --- |
| `ONE_DAY_PLAN.md` | this folder | The hands-on material she follows |
| `TRAINER_GUIDE.md` | this folder (this file) | Your facilitation script |
| `README.md` | this folder | Architecture overview, points here from both other docs |
| `backend/README_ELASTICSEARCH.md` | `backend/` | Exact Elasticsearch install/config steps for Hour 2-3 |
| `artefacts/opening-speech.html` | `artefacts/` | Speaker script for the first 15 minutes — open in a browser |
| `artefacts/architecture-diagram.html` | `artefacts/` | Visual ingestion/query flow diagram — open in a browser |
| This repo, on her machine | — | The actual code |
| Your tested OpenAI API key | — | Nothing works without it |

---

## Part 5 — Closing the session

Spend the last 10 minutes on three things, in this order:

1. **Recap the architecture out loud, from her.** Ask her to draw or
   describe the four boxes (React → FastAPI → vector DB → OpenAI) from
   memory. This is the real check for whether the day worked.
2. **Name what she can do next**: point her at the "Extending this project"
   section in `README.md` — swap in her own real documents, try changing
   `top_k`, try the Chroma-vs-Elasticsearch comparison table. Concrete next
   steps beat "let me know if you have questions."
3. **Ask what confused her.** Write it down. It's the most useful feedback
   you'll get for improving this guide the next time you run it.

---

## Part 6 — If you're running this for more than one person

Everything above assumes one learner driving one keyboard. For a small
group:

- One Elasticsearch instance and one backend can serve multiple people if
  they're all on the same network — but the whole point of this exercise is
  each person building their own end to end, so prefer everyone running
  their own full stack if laptops allow it.
- Pair people up (driver/navigator, swap halfway) rather than having anyone
  purely watch — the facilitation rules in Part 3 apply per pair, not per
  room.
- Budget extra time for Hour 2-3 — Elasticsearch heap-size and port
  conflicts are exactly the kind of issue that's different on every laptop,
  so multiply your single-person time estimate, don't just add a fixed
  buffer.
