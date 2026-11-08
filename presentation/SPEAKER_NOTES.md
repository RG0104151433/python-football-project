# Speaker notes — first presentation draft

Suggested total: 10 minutes. These are proposed speaking roles and rehearsal timings, not a record of actual speaking time or independent member verification. Audience text is English; the class name remains 睿信2526班.

## 1. The opening fixture
Presenter: Wenyu Jiang · suggested slot 0:00–0:50

Start with England against Croatia. Ask the room to choose a home win or a draw/away win. Do not reveal our probability yet. The question is not whether home teams sometimes win more often, but whether historical patterns still help once we account for ability.

## 2. Data to evidence
Presenter: Ruiyi Gao · suggested slot 0:50–1:40

Reveal the preparation steps one at a time. The raw snapshot covers far more years than the comparison sample. Neutral and earlier matches can help us learn strength, while the historical home-win comparison excludes neutral venues. The learning and comparison sets overlap; do not add their counts.

## 3. Historical patterns
Presenter: Ruiyi Gao · suggested slot 1:40–2:50

Start with eras. Switch briefly to match types or geography, then reveal composition adjustment. A different mix of opponents or tournaments can change a rate. These descriptions are useful, but not causal home effects. We also tested conditional uncertainty; broad ranges limit strong claims about long-term change.

## 4. Learning mechanism
Presenter: Ruiyi Gao · suggested slot 2:50–4:10

Click through the five stages. Before the game we estimate both teams and uncertainty, then include venue/context and issue probabilities. After observing actual results we update for later games. All games on a date are predicted first. Friendly results carry less information. Unexpected results can be noise, or repeated evidence of a genuine change. This animation explains the workflow; it is not new training.

## 5. Strength over time
Presenter: Ruiyi Gao · suggested slot 4:10–5:05

Play the archived years, then pause. Switch to Japan if useful. Every dot is a selected pre-match estimate. Both home and away games supplied learning information. Whiskers show uncertainty about the estimate, not a score range or a world ranking. Do not discuss a specific historical cause that we did not test.

## 6. Same-match comparison
Presenter: Zhenglin Chen · suggested slot 5:05–6:40

Reveal the three predictors in order. They face exactly the same matches and binary target. The largest difference is associated with strength. Context adds a smaller reduction in log loss. The two percentage reductions have different baselines and cannot be added. Switch to accuracy: 70.01% is home win versus non-home win, not full win/draw/loss accuracy. The archive was reused in development, so the small gain is not a guaranteed future benefit.

## 7. History and computation
Presenter: Zhenglin Chen · suggested slot 6:40–7:35

The first part of each label is strength history, the second is the outcome-fitting history. Click all/all, then all/12y. Cumulative history won among the tested combinations; this does not mean all old games have equal current influence. The controlled outcome-fitting component became about two-thirds cheaper with twelve years, at a small probability-score cost. This is not total model runtime.

## 8. Regional limits
Presenter: Zhenglin Chen · suggested slot 7:35–8:30

Select Africa to show why pooled performance is incomplete. Its contextual increment changes direction under some year/team deletions; strength itself is not invalidated by that finding. Select Oceania if time permits: the sample is only 148 matches and required cells can disappear. These checks change evaluation composition without retraining history. They do not prove causal regional differences.

## 9. Issued forecasts
Presenter: Wenyu Jiang · suggested slot 8:30–9:25

Return to England–Croatia and reveal the range. The central main probability is about 63.50%, but the latent-strength range crosses 50%. It is a probability statement, not a confident promise. If asked, select Ukraine–Georgia: the main model withheld its estimate under the venue rule; the optional three-way output belongs to a separate auxiliary rating model. We issued 49 main forecasts for 52 fixtures and did not yet evaluate actual results.

## 10. Takeaways
Presenter: Wenyu Jiang · suggested slot 9:25–10:00

Close with the three contributions: understand composition, estimate uncertain changing strength, and communicate probabilities with limits. The next step is to evaluate genuinely new outcomes and improve the joint win/draw/loss and calibration models. Those are prospects, not implemented gains. Thank the audience.
