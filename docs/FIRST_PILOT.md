# First real pilot checklist

The quickstart runs on synthetic data and only proves the code works. This is the path for your own work. Plan 60 to 90 minutes for the sample and labelling, plus time to find evidence. Nothing here has been run on a real log yet, so treat the times as a guess.

You need: one person who made the asks, access to the evidence sources (git, the ticket tracker, the live system), and a place outside this repo to keep your log and notes.

1. **Pick a window.** Freeze one week of asks. Write the start and end down.
2. **Decide what counts as an ask.** One sentence. Filler such as "ok" and "thanks" does not count. Write the rule down before sampling.
3. **Export the asks** to the log format in [SCHEMA.md](SCHEMA.md), one `ask` row each. Keep the file out of this repo and out of any public place.
4. **Draw the sample** with a recorded seed: `python -m factory_kit sample` (see `--help`). Save the seed and the number of asks you drew from.
5. **Label each row** with one of the six labels in [GLOSSARY.md](GLOSSARY.md). Fill `evidence_kind` and `evidence_ref`. Judge against git, tickets or the live system, not the agent's say-so.
6. **Score it** with `sample --score`. Record the loose share, the strict share and their intervals, and the sample size next to every number.
7. **Check the privacy rule** before sharing anything: run `python scripts/privacy_scan.py` with your own deny list on whatever you plan to publish.
8. **Write down one change** to how you record work, and the date you will measure again.

Done when you have: the seed, the denominator, both shares with intervals, and one intervention. Do not quote a before and after change from one run.
