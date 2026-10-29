# Brief: round 6

## Asked
Seven fix-ups to do first, then two new app types. The fix-ups cover number formatting by column role, pluralising, Explorer bar-click styling, where "score" captions appear, line chart y-range, the PPTX title slide, and one ARCHITECTURE.md edit. The new apps are Monitoring (rule R4) and Survey (rule R5), added to the ordered rule table before Explorer. Everything earlier rounds built and the business's branding stay as they are; only what these suggestions ask changes.

## Deliverable
A change to the existing product: seven fix-ups, two new app types (Monitoring and Survey), QA fixtures and tests, and edits to DESIGN.md and ARCHITECTURE.md. The idea does not say what kind of product it is.

## Done when
- Separators appear only for numeric columns. Identifier, temporal and year-like columns never get them ("2,024" never appears) in tables, the side panel and tooltips.
- Counts are pluralised correctly ("1 point", "1 row"). "score 0.xx" shows only in Explorer captions, not in Business or Map.
- Explorer bars get the bar-click class and pointer like Business. Line charts keep the auto y-range, with a zero baseline for bars only. DESIGN.md is updated for both (AC-39 for the bars).
- The PPTX title slide shows the file name as a smaller second line. ARCHITECTURE.md L147-148 says hexagon choropleth cells.
- R4 Monitoring (T>=1, N>=1, C=0) has:
  - one sparkline tile per numeric column, showing latest, min, max and change vs previous period (arrow plus text);
  - a period selector (7/30/90 days, all);
  - a main line with a rolling mean;
  - spikes flagged where |z|>3 on a 30-point rolling window (marker plus "spike" label, never colour alone).
- R5 Survey (C>=4, categoricals >=60% of columns, N<=2) has:
  - one horizontal bar per question, sorted by count, in a small-multiples grid;
  - Likert questions (agree/disagree scales or 1-5) as a 100% stacked bar in scale order, on a diverging palette with a grey neutral;
  - a cross-tab picker (two dropdowns) giving a count heatmap with row %.
- Both new apps have a View-as switch and a table toggle. Exports are titled "Monitoring overview" and "Survey overview".
- QA has one fixture per new archetype, week and year grain tests, and an Explorer-only XLSX/PPTX case.

## Unclear
- What do T, N and C stand for in the rules (presumably temporal, numeric and categorical column counts)? The idea does not define them.
- What is the existing rule table, and where do R4 and R5 sit relative to R1-R3? "Before Explorer" is the only placement given.
- What does the "View-as switch" switch between? The idea does not say.
- What does the "bar-click class/pointer" do in Business, and what should clicking an Explorer bar do?
- How should "year-like" columns be detected, given that the idea rejects regex and wants column roles?
- What are "week and year grain tests"? The idea does not say which feature has a grain.
- Does "change vs previous period" compare the whole selected period or the last two points, and what happens for "all"?
- What counts as a Likert scale beyond "agree/disagree scales or 1-5"? What happens to a question that is only partly Likert?
- What does "trends off" mean in the Team line?
- Should the new apps be exportable to XLSX and PPTX, or only titled? "Exports" is not defined.

## Not asked
- No changes to earlier rounds' features or to the business's branding.
- No new app types beyond Monitoring and Survey.
- No zero baseline on line charts.
- No "score 0.xx" captions in Business or Map.
- No trend features ("trends off").
- No roles beyond designer, frontend and backend.
