# Desktop QA — 1440×900

## Result

PASS. The local Streamlit Home page was inspected and measured at a 1440×900 CSS-pixel viewport.

- Viewport width: 1440px
- Document width: 1440px
- Body width: 1440px
- Horizontal overflow: none
- Default Week 18 cards: 11
- Category sections: 4
- Category grid: two columns of approximately 479px each
- Browser console errors: 0

Desktop retains the normal public sidebar and uses a two-column report grid. The card data is the same shared payload used by mobile; only the structural layout changes at the breakpoint.

## Captures

- Exact 1440×900 test capture: `C:/Users/tucka/.codex/visualizations/2026/07/13/019f5b96-e395-7e33-a29e-6332bbea27e9/desktop_home.png`
- Full desktop overview capture: `C:/Users/tucka/.codex/visualizations/2026/07/13/019f5b96-e395-7e33-a29e-6332bbea27e9/desktop_home_overview.png`

## Supporting-route check

The Player, Team, and Game evidence routes were opened from Home during portrait QA. Their query-state behavior is shared with desktop, and no supporting-page layout was redesigned.
