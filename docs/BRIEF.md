# Brief: round 4

## Asked
Make the dashboard assemble itself with fixed rules, no AI, offline and with no new dependencies. Each chart gets a deterministic interest score from 0 to 1, and the scores decide the layout: the top chart goes full width and the rest sit in a 2-column grid (1 column on phones). A KPI strip goes at the top. Filters (dropdowns and a date range) are applied server-side and kept in the URL, clicking a bar or donut slice cross-filters everything, and the XLSX/PPTX exports respect the active filters.

## Deliverable
A change to the existing dashboard web app (frontend, backend and design work), plus tests. The team is designer + frontend + backend, with trends off.

## Done when
- Each chart kind gets its score by the stated rule: line = |Spearman rho| of value vs time; bar/donut = Gini of category totals; scatter = |Pearson r|; histogram = min(1, |skew|/3); heatmap = max off-diagonal |r|; maps = 0.6; table is always last.
- Charts are ordered by score, ties broken by the existing fixed chart order, and the same data always gives the same order.
- The highest-scored chart is full width and the others are in 2 columns (1 on phones). Each chart's caption shows its score, e.g. "Rule: temporal + numeric · score 0.82".
- The KPI strip shows rows, columns, % missing, then the sum of the first 3 numeric columns with thousands separators.
- There is one dropdown per categorical column (<=50 distinct values) and a date range if a temporal column exists. Filters go through the existing chart route as query params, the URL holds the state (shareable, back button works), and a "Clear filters" button resets them.
- Clicking a bar or donut slice sets that category filter and redraws every chart and KPI.
- XLSX and PPTX exports use the active filters, and the title slide / summary sheet lists them.
- Filtering and redrawing take under 1 s on 200,000 rows.
- Tests cover: score per chart kind on fixture data, order stability, filter changes counts, click sets filter, exports honor filters, and no external network requests.

## Unclear
- Which value column and which time column does the line chart use when there is more than one of each?
- Is the Gini for bar/donut computed on the same category totals the chart draws?
- Do the KPI figures (rows, % missing, sum) reflect the active filters? "Redraws every chart and KPI" suggests yes.
- What is the score and caption for the table, which is "always last"? And what happens when a chart kind is absent or its inputs are degenerate (e.g. constant data, fewer than 2 points)?
- Can a cross-filter be removed by clicking again, or only with "Clear filters"? Can several categories be picked in one dropdown?
- Does clicking a bar or donut on a column with more than 50 distinct values still set a filter, given it has no dropdown?
- When no filters are active, what should the exports' title slide / summary sheet say?
- What counts as a phone width, and what is the hardware for the 1 s target?
- What does "trends off" mean in practice? The idea does not say.

## Not asked
- Any AI or machine-learning recommendation, any new dependency, or any network request.
- Removing or changing earlier rounds' features, or changing the business's branding.
- Charts or scores beyond the kinds listed; a user-adjustable scoring.
- Filter types other than categorical dropdowns and a date range.
- Anything for trends.
