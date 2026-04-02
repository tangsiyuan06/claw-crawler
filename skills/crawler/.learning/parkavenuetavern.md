---
name: parkavenuetavern
description: Menu scraping from parkavenuetavern.com - WordPress + Enfold theme
type: reference
url: https://parkavenuetavern.com/nyc/menu/
---

## Park Avenue Tavern Menu Scraping

### Site Info
- **URL**: https://parkavenuetavern.com/nyc/menu/
- **Platform**: WordPress + Enfold theme
- **Date**: 2026-04-02

### Structure
The menu page uses Enfold's **Tab Section** element (`av-tab-section`) with 6 tabs:
1. ALL DAY MENU (default active)
2. BRUNCH
3. BEVERAGES
4. DESSERTS
5. KIDS MENU
6. LATE NIGHT MENU

### DOM Pattern
Menu items use a consistent pattern:
- Category titles: `<h2 class='av-special-heading-tag'>CATEGORY NAME</h2>`
- Item names: `<h6 class='av-special-heading-tag'>ITEM NAME<span class="menu-price">PRICE</span></h6>`
- Descriptions: `<div class='av_custom_color av-subheading av-subheading_below'><p>description</p></div>`

### Scraping Approach
- **SSR available** - all menu data is in the initial HTML response
- No JavaScript/browser needed - simple `requests` + `BeautifulSoup` works
- Tab content is all rendered server-side in the same page
- Price is embedded inside the h6 tag as `<span class="menu-price">`

### Key Takeaways
- WordPress + Enfold theme renders tab content server-side
- Menu uses `av-special-heading` elements with `menu-tittle` class for items
- Price extraction: find `span.menu-price` within h6 headings
- The page also has PDF download links at the bottom
