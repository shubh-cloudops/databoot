# Round 4: the Board's suggestions

Round 4: self-assembling dashboard (rule-based visualization recommender, NO AI, offline, no new dependencies).
1. Interest score 0..1 per chart, deterministic:
   line = |Spearman rho| of value vs time; bar/donut = Gini of category totals; scatter = |Pearson r|;
   histogram = min(1, |skew|/3); heatmap = max off-diagonal |r|; maps = 0.6 fixed; table = always last.
   Ties broken by the existing fixed chart order. Same data must always give the same order.
2. Layout from score: highest-scored chart full width, the rest in a 2-column grid (1 column on phones). Rule caption shows the score, e.g. "Rule: temporal + numeric · score 0.82".
3. KPI strip at the top: rows, columns, % missing, then sum of the first 3 numeric columns (thousands separators).
4. Filters: one dropdown per categorical column (<=50 distinct) plus a date range if a temporal column exists. Applied server-side via the existing chart route with query params; state kept in the URL (shareable, back button works). "Clear filters" button.
5. Cross-filter: clicking a bar or donut slice sets that category filter and redraws every chart and KPI.
6. XLSX/PPTX exports use the active filters, and the title slide / summary sheet lists them.
7. Performance: filter + redraw under 1 s on 200,000 rows.
Tests: score per chart kind on fixture data, order stability, filter changes counts, click sets filter, exports honor filters, no external network requests.
Team: designer + frontend + backend; trends off.

Keep everything the earlier rounds built and the business's branding; change only what these suggestions ask.
