# Brief: round 5

## Asked
Make the app pick a layout for each dataset by fixed rules, with no AI, offline and no new dependencies. A dataset is assigned an archetype from its column roles (T temporal, N numeric, C categorical, G lat+lon pair, I identifier/text). The first matching rule wins:
- R1: G present and (N<=2 or at least 50% of rows have coordinates) -> Map app.
- R2: T>=1 and C>=1 and N>=1 -> Business app.
- R3: otherwise -> Explorer (the round 4 dashboard, unchanged).

The detector is an ordered rule table. Rules R4-R7 (Survey, Directory, Monitoring, Drive) are reserved for round 6 and must be able to plug in later. The page shows a badge such as "App: Business (rule R2)" and a "View as" switch that lists only the archetypes the dataset qualifies for. The choice is kept in the URL.

Business app: KPI cards (primary amount for the latest full period, change vs previous period as arrow icon + signed % + text label, sparkline); a trend of amount by period (auto grain day/week/month/year, one y-axis, small multiples for several measures, never a dual axis); a leaderboard (horizontal bars, top 10 descending, direct value labels, rest folded into "Other"); drill-down (clicking a bar re-groups by the next categorical column, with a breadcrumb back); a change table (category, previous period, latest period, delta, delta on a diverging scale with grey at zero).

Map app: map at about 70% of viewport height with a bundled offline outline; points coloured by the primary numeric on a single-hue sequential scale; above 5,000 points, density/hexbin cells instead of overplotting; side panel with details of the clicked point plus a top-regions bar chart; the 3D view stays available as a toggle.

Global chart rules go into DESIGN.md and apply to every app and to Explorer (see Done when). XLSX/PPTX exports follow the archetype's section order and title ("Business overview", "Map overview").

## Deliverable
A change to the existing app (earlier rounds' work): a rule-based archetype detector, a Business app layout, a Map app layout, chart rules in DESIGN.md, archetype-aware XLSX/PPTX exports, and tests. Team named: designer + frontend + backend; trends off.

## Done when
- One fixture per archetype produces the expected app, and detection gives the same result every time.
- The badge shows the app and rule, and the "View as" switch lists only qualifying archetypes and works; the choice is in the URL.
- Business app has the KPI cards, trend, leaderboard, drill-down with breadcrumb, and change table as described.
- Map app has the 70%-height map, sequential colouring, hexbin/density above 5,000 points, side panel, and the 3D toggle.
- No figure has a second y-axis (no yaxis2), every chart has a hover tooltip and a "view as table" toggle, and thousands separators are used everywhere.
- XLSX/PPTX exports follow the archetype's section order and title, DESIGN.md holds the global chart rules, and the app makes no network requests.

## Unclear
- What counts as a "latest full period" and the "previous period" when the data ends mid-period?
- Which numeric is the "primary" amount or primary numeric, and how is it chosen?
- Which categorical column is "next" for drill-down, and what happens at the last level?
- How are "top regions" defined for the Map app, and from which column?
- How are column roles assigned (e.g. what makes a column I rather than C)?
- If a dataset is Explorer-only, does "View as" show a single option or hide?
- What exports should look like for Explorer, which has no named title in the idea?
- Hexbin cell size and the exact density visual are not specified.
- "Trends off" is not defined.

## Not asked
- Rules R4-R7 (Survey, Directory, Monitoring, Drive); only the table's room for them.
- Any AI or generative model use, online services, or new dependencies.
- Changes to the Explorer dashboard, earlier rounds' features, or the business's branding beyond what is listed.
- A dual y-axis or colour-only signalling of change.
