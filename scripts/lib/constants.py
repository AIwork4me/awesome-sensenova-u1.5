GAP_ALLOW = -0.5
PARITY_RATIO = 0.8
MAX_REWRITE_ROUNDS = 3
SEEDS_PER_PROMPT = 2
PILOT_SIZE = 30
# Arbitration rule (historical, see results/judge/JUDGE-RUN-MANIFEST.json):
# trigger a third arbitration review when
#   abs(mean5(scores_original) - mean5(scores_resample)) > ARBITER_MEAN_DIFF
# i.e. the threshold applies to the absolute five-dimension MEAN score
# difference, not to any single dimension.
ARBITER_MEAN_DIFF = 2.0
RESAMPLE_RATE = 0.1
