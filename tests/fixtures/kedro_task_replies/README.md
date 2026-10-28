The three replies qwen2.5-coder (7b, Ollama, temperature 0) gave on 28 Oct 2026 for kedro's
standing violation `kedro.runner -> kedro.framework.project` (three import lines in
kedro/runner/task.py at lines 24, 76 and 111). Kept verbatim as a regression fixture: the draft
step must reject all three for the right reasons (1 and 3: FIND text joins non-adjacent lines;
2: the forbidden module is still imported). Verdict on the laptop: escalate after 112 s.
