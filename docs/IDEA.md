# Round 5: the Board's suggestions

Round 5: data-driven app archetypes (generative UI by rules, NO AI, offline, no new deps).
1. ARCHETYPE DETECTION per dataset, deterministic, first match wins, using column roles (T temporal, N numeric, C categorical, G lat+lon pair, I identifier/text):
   R1 G present and (N<=2 or >=50% of rows have coordinates) -> Map app
   R2 T>=1 and C>=1 and N>=1 -> Business app
   R3 else -> Explorer (the round 4 dashboard, unchanged)
   Rules R4-R7 (Survey, Directory, Monitoring, Drive) are reserved for round 6; design the detector as an ordered rule table so they plug in.
   Page shows a badge "App: Business (rule R2)" and a "View as" switch listing only the archetypes this dataset qualifies for. Choice kept in the URL.
2. BUSINESS APP layout:
   - KPI cards: primary amount for the latest full period, change vs previous period as an arrow icon + signed % + text label (never colour alone), sparkline.
   - Trend: amount by period (auto grain day/week/month/year), one y-axis. Several measures -> small multiples, NEVER a dual axis.
   - Leaderboard: horizontal bars, top 10 categories sorted descending, direct value labels, the rest folded into "Other".
   - Drill-down: clicking a leaderboard bar re-groups by the next categorical column, with a breadcrumb to go back.
   - Change table: category, previous period, latest period, delta; delta coloured on a diverging scale with grey at zero.
3. MAP APP layout:
   - Map uses ~70% of the viewport height (bundled offline outline). Points are coloured by the primary numeric on a single-hue sequential scale.
   - Over 5,000 points: aggregate into density/hexbin cells instead of overplotting.
   - Side panel: details of the clicked point plus a top-regions bar chart. The 3D view stays available as a toggle.
4. GLOBAL CHART RULES (write into DESIGN.md, applied to every app and to Explorer):
   magnitude = sorted bars with a zero baseline; change over time = line; part-to-whole = stacked bar, donut only for 2-5 parts;
   one y-axis always; fixed categorical palette order, max 8 then "Other"; max 3 colour series on scatter and maps;
   sequential = one hue light to dark; diverging = two hues with a grey midpoint; legend when >=2 series plus direct labels when <=4;
   every chart has a hover tooltip and a "view as table" toggle; thousands separators everywhere.
5. Exports: XLSX/PPTX follow the archetype's section order and title ("Business overview", "Map overview").
Tests: one fixture per archetype gives the expected app; detection stable; the View-as switch works; no figure anywhere has a second y-axis (no yaxis2); drill-down and breadcrumb; hexbin above 5,000 points; every chart has a table toggle; no network requests.
Team: designer + frontend + backend; trends off.

Keep everything the earlier rounds built and the business's branding; change only what these suggestions ask.
