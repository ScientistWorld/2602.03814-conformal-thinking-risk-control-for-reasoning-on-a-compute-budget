# Scientist Constraints

These constraints define what future scientist agents must hold fixed when trying to improve the benchmark. The goal is to improve adaptive reasoning-budget control, not to win by changing the task, scaling the model, or using extra labels.

## Model

Use the same base reasoning model for a given experiment as the benchmark run. The paper's main settings use Qwen3-8B, Qwen3-30B-A3B, DeepSeek-R1-Distill-Qwen-32B, and Qwen3-VL-8B; a reproduced gym may implement a subset, but each scored experiment must name the exact model and checkpoint.

Do not replace a scored model with a larger or stronger model to improve accuracy or calibration. Model swaps change the underlying reasoning trajectories and make token-efficiency comparisons invalid. A scientist may add lightweight stopping, calibration, or signal-processing components around the fixed model, but the base model weights used to generate answers must remain fixed.

## Data

Use the same datasets and splits supplied by the gym for each experiment. The paper evaluates AIME 1983-2025, DeepScaleR with AIME removed, GPQA-Diamond, and MathVision. If the reproduction uses a smaller or substitute accessible subset, that subset becomes the fixed benchmark for future submissions.

Do not add external labeled examples to calibrate stopping decisions, train auxiliary predictors, or choose operating points. Additional unlabeled reasoning trajectories from the same fixed prompts are allowed only if the benchmark explicitly permits regenerating trajectories under the same base model and decoding settings.

## Validation and Test Separation

Validation labels may be used only for selecting stopping configurations. Test labels must be used only by the evaluator. Reusing test labels to tune risk tolerances, signal choices, or operating points invalidates the score.

Repeated split experiments must use the provided split seeds. If a new split suite is added, it must be committed as benchmark data before scoring and used unchanged by all methods.

## Generation Protocol

Use the same prompt format, maximum reasoning budget, chunking rule, answer-extraction rule, and decoding configuration for all compared policies within an experiment. The paper chunks trajectories by blank-line-delimited reasoning segments and elicits boxed final answers; a reproduced benchmark should keep its chosen equivalent fixed.

Do not reduce token use by changing the model prompt to suppress reasoning, using a different decoding strategy, shortening the maximum budget, or changing answer formatting unless every baseline and candidate policy is regenerated under the same changed benchmark definition.

## Metrics

Report both compute benefit and risk constraints. A submission that improves token savings while exceeding the target false positive or false negative risk should score worse, not better.

Do not score wall-clock speed as a primary result. Use machine-independent quantities such as generated token count, stopping chunk index, risk, accuracy, and normalized efficiency loss.

## Compliance Checklist

- [ ] Exact base model checkpoint is unchanged for each scored experiment
- [ ] No larger model or external solver is used to generate answers
- [ ] Only the benchmark's allowed validation data is used for calibration
- [ ] Test labels are not used for selecting signals, tolerances, or operating points
- [ ] Prompt, decoding settings, chunking, answer extraction, and maximum budget match the benchmark definition
- [ ] Reported improvements include risk metrics as well as token-efficiency metrics
- [ ] Token savings are measured with generated token counts, not wall-clock time
