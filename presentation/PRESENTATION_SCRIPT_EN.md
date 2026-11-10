# V5 presentation script — plain English

This is the first full speaking draft for the 14-screen V5 presentation. Use rehearsal to check the total time; shorten optional detail if the course limit is 10 minutes. Bracketed lines are stage directions, not spoken words. Slide numbers match the HTML. No actual match results have been supplied yet.

## 1 · The sealed envelope — about 30 seconds

[Click “Open the research question”.]

Good morning, everyone.

Before a football match, we often ask: who will win?

Our project asks a more useful question: what can past results tell us before the match starts, and how sure should we be?

We saved predictions for 52 Nations League matches on November 2. Today, we will explain where those predictions came from and how we check them against completed matches.

## 2 · Our data — about 40 seconds

[Select each ring. Point to one segment.]

We started with an archive of almost fifty thousand international matches.

We kept the original files and recorded checks of dates, scores, team names, and match locations.

About twenty-five thousand matches were used to compare home-win patterns. About thirty-nine thousand were used to learn team strength. That includes earlier and neutral-venue matches.

These samples overlap. We cannot add the two numbers together.

## 3 · Time and match type — about 50 seconds

[Show all matches, then add the friendly and other-match lines.]

First, we looked at home-win rates in different periods.

The blue line shows all matches. The orange line shows friendlies. The green line shows other matches.

The lines move differently. The mix of match types may affect the overall pattern.

Across the whole sample, home teams won less often in friendlies. The gap was about 3.25 percentage points. For example, 50 percent and 53 percent differ by three percentage points.

When we gave the two groups the same mix of periods, the gap became about 2.88 percentage points.

That is a smaller gap, but it does not prove that being a friendly caused the difference.

[Optional: open the Question 4 button.]

Repeated teams and shared conditions make matches dependent. We checked uncertainty, but some ranges were too wide for a clear conclusion.

## 4 · Geography — about 45 seconds

[Hover over Europe or Asia. Switch the two views once.]

Next, we compared geographic groups.

The first view groups matches by the home team's region. The second groups them by the opponent's location: outside the continent, another part of the same continent, or the same part.

These are different questions. A region's home-win rate can change when its opponents change.

The map follows our study rules. Turkey is in Southern Europe, Iran is in Western Asia, and Australia is in South-eastern Asia.

These are sample results, not a ranking of regions.

## 5 · What a strength model must consider — about 45 seconds

[Reveal the four factors in order.]

To make a prediction, we need more than a past home-win rate.

First, we need to consider the opponent. Beating a strong team provides different evidence from beating a weak team.

Second, location matters. We use information from home, away, and neutral matches.

Third, not all games carry the same information. Friendlies may involve experiments with players and tactics, so we give them less weight.

Finally, national teams do not play on a regular weekly schedule. The club calendar here helps show the contrast. Long gaps make the timing of the evidence important.

## 6 · What “strength” means — about 60 seconds

[Select Brazil, then China or South Africa. Play a few years.]

Our strength value is not a world rank. It is also not a predicted number of goals.

It is an estimate of a team's ability, based on results available before each match.

A higher value means the model expects a stronger performance against the same opponent under the same conditions. Zero is only a reference point.

The line changes as new results arrive. The small vertical lines show how uncertain the estimate is.

Both teams learn from a match. We first make the prediction. We then observe the real result and use it for later predictions.

## 7 · Comparing three prediction methods — about 60 seconds

[Play part of the year-by-year chart. Point to the comparison on the right.]

We compared three methods on the same historical matches.

The first uses background information, such as period, match type, and region. The second uses team strength. The third combines strength and background.

For this comparison, we asked a two-way question: will the home team win, or not? A draw and an away win are both in the second group.

The combined method reached about 70 percent accuracy. Strength provided most of the improvement. Adding background gave a smaller extra gain.

We also checked probability quality. Choosing the right side is not enough; the probabilities should make sense too.

Yearly results vary. These records also helped us choose the model, so they are not a completely new test.

## 8 · How much history to keep — about 45 seconds

[Raise the bars in order. Read the exact score beside the graph.]

How far back should we look?

Too little history throws away useful evidence. Older matches may describe a different team.

We tested six combinations. One choice controls the history used to estimate strength. The other controls the history used to turn that strength into a match probability.

The bars show improvements in probability quality. The loss on the right should be lower. It is not an accuracy percentage.

Among these choices, keeping the full history remained our default. But we did not find one fixed number of years that must be best for every future situation.

## 9 · Our saved predictions — about 50 seconds

[Hover over a fixture. Switch view, then hover again.]

Here are the 52 predictions saved before the matches.

In this view, we show separate probabilities for a home win, a draw, and an away win. These come from our supporting three-way model.

In the other view, the main model predicts a home win versus a non-home win.

The red point is the home-win probability. The purple line shows a range caused by uncertainty about team strength. It does not cover every possible source of error.

For three matches, the main model did not give a prediction under our venue rule. We keep those cases visible instead of filling in a number.

The large box makes each saved prediction easier to inspect.

## 10 · Checking the results — about 60 seconds

[Before the talk: import the checked CSV. During the talk: choose the main binary rule first.]

We decide how to judge a prediction before we count the results.

For the main model, a home-win probability of at least 50 percent counts as a home-win pick. Otherwise, the pick is a draw or an away win.

We compare that pick with the final score after 90 minutes, including added time.

We leave unfinished or unverified matches out of the count. We also exclude the three matches without a main prediction.

[Choose ONE of the following result paragraphs. Replace every bracketed value with the displayed totals before rehearsal. Do not read the directions or placeholders aloud.]

**If verified results are available:**

We have checked [N] matches for the main model. It picked [C] correctly and [W] incorrectly, giving an accuracy of [A] percent. Another [P] fixtures are still pending. The supporting three-way model has a separate result because it answers a different question.

**If no verified results are available:**

We have not yet entered verified results, so we cannot report an accuracy figure for these fixtures. The predictions remain saved, and this page is ready for the final scores.

**Continue in either case:**

A few matches cannot prove that a model always works. We show wrong picks too.

## 11 · Our research process — about 25 seconds

[Reveal the eight steps.]

This is the path we followed.

We preserved and checked the data, compared historical patterns, and studied their uncertainty.

We then estimated changing strength and compared prediction methods. After checking history length and geographic scope, we saved future predictions.

The last step is to compare them with verified outcomes. We keep this separate from making the predictions.

## 12 · Our repository — about 25 seconds

[Open Repository structure, then return.]

The repository keeps the work connected.

It contains the data, code, results, paper, presentation, and our main decisions.

This directory tree shows where to find those materials. The links show folders and files.

You are welcome to explore the project on GitHub.

## 13 · Three findings — about 35 seconds

We have three main findings.

First, a historical home-win rate reflects both team strength and the mix of matches. It does not, by itself, measure a pure home advantage.

Second, strength provides most of the useful information in our prediction comparison. Background adds a smaller improvement.

Third, there is no simple rule that works equally well for every history length or region. We need to explain uncertainty and show where our evidence is limited.

## 14 · Thank you — about 10 seconds

Thank you for listening.

We welcome your questions and suggestions.

---

## Short answers for likely questions

**Is 70 percent the accuracy for home win, draw, and away win?**

No. It is historical accuracy for home win versus non-home win. The three-way model is evaluated separately.

**Is your strength number an Elo score?**

No. It is a changing estimate on our model's own shared scale, with uncertainty.

**Does a correct pick prove the probability was right?**

No. One match gives only one result. We need many predictions to judge the probabilities.

**Why keep old matches?**

They still contain information. Our model allows strength to change. In the choices we tested, cutting history did not clearly improve the default.

**Did you use machine learning?**

Yes. The model learns from earlier results and updates when real results arrive. We also used historical prediction checks to compare settings. We did not use a large neural network.

**What do the uncertainty ranges mean?**

They show how uncertain strength estimates affect the main predicted probability, with other model settings fixed. They are not ranges of possible scores.

## Rehearsal notes

- Bracketed lines are actions or placeholders, not spoken text.
- Use only a few map examples and country curves. Do not click every option.
- The result paragraph must match the selected rule and current totals. Never mix the binary and three-way denominators.
- Keep the V4 backup. Use the V5 file and checked results CSV on the actual presentation computer.
- This is an untimed draft. Shorten optional detail after a real rehearsal rather than claiming it already fits the time limit.
