# Round 6: the Board's suggestions

Round 6, part 1 FIX-UPS (do first):
1. Number formatting by column ROLE, not regex: separators only for numeric columns; never for identifier, temporal or year-like columns (no "2,024"), in tables, side panel and tooltips.
2. Pluralise: "1 point", "1 row".
3. Explorer bars get the bar-click class/pointer like Business; update DESIGN.md AC-39.
4. "score 0.xx" only in Explorer captions; none in Business/Map.
5. Line charts keep auto y-range (zero baseline is bars only); DESIGN.md says so.
6. PPTX title slide: file name as a smaller second line.
7. ARCHITECTURE.md L147-148: hexagon choropleth cells.
Part 2 NEW APPS (add to the ordered rule table before Explorer):
 R4 Monitoring: T>=1, N>=1, C=0 -> one sparkline tile per numeric (latest, min, max, change vs previous period with arrow + text), a period selector (7/30/90 days, all), main line with a rolling mean, and spikes flagged where |z|>3 on a 30-point rolling window (marker + "spike" label, never colour alone).
 R5 Survey: C>=4, categoricals >=60% of columns, N<=2 -> one horizontal bar per question, sorted by count, in a small-multiples grid. Likert detection (agree/disagree scales or 1-5): 100% stacked bar in scale order on a diverging palette with a grey neutral. Cross-tab picker: two dropdowns -> count heatmap with row %.
 Both: View-as switch, table toggle, exports titled "Monitoring overview" / "Survey overview".
QA: one fixture per new archetype; week and year grain tests; Explorer-only XLSX/PPTX case; "2,024" must never appear for a year column.
Team: designer + frontend + backend; trends off.

Keep everything the earlier rounds built and the business's branding; change only what these suggestions ask.
