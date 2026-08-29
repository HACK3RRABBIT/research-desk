/* Frontend copy of profile.INTEREST_CATEGORIES. Keep in sync with
   research_desk/profile.py — the backend validates selections against its own
   copy, and the picker here renders the same (tag,label) structure. */

export const INTEREST_CATEGORIES = [
  { label: "Energy & Commodities", items: [
    ["energy","Energy"], ["oil","Oil"], ["gas","Gas & LNG"], ["uranium","Uranium / Nuclear"],
    ["renewables","Renewables"], ["electricity","Electricity & Grid"], ["shipping","Shipping & Maritime"], ["commodities","Commodities"],
  ]},
  { label: "Markets & Money", items: [
    ["markets","Global markets"], ["stocks","Equities"], ["crypto","Crypto / Digital assets"],
    ["rates","Rates & bonds"], ["inflation","Inflation & CPI"], ["central_banks","Central banks"],
    ["macro","Macro economy"], ["debt","Debt"],
  ]},
  { label: "Geopolitics", items: [
    ["geopolitics","Geopolitics"], ["iran","Iran"], ["china","China"], ["russia","Russia"],
    ["us_policy","US policy"], ["europe","Europe"], ["middle_east","Middle East"],
    ["nato","NATO / Defense pacts"], ["trade","Trade & tariffs"], ["india","India"],
  ]},
  { label: "Security & Defense", items: [
    ["security","Security"], ["defense","Defense & arms"], ["military","Military operations"],
    ["cyber","Cyber / Infosec"], ["intelligence","Intelligence & signals"], ["sanctions","Sanctions & export controls"],
  ]},
  { label: "Technology", items: [
    ["ai","AI / Machine learning"], ["x","X / Twitter"], ["tech_platform","Tech platforms"],
    ["semiconductors","Semiconductors / chips"], ["space","Space & launch"],
    ["telecom","Telecom & networks"], ["software","Software & cloud"],
  ]},
  { label: "Science & Climate", items: [
    ["climate","Climate & environment"], ["health","Health & biotech"],
    ["science","Science"], ["energy_tech","Energy tech"],
  ]},
  { label: "Regions", items: [
    ["mena","Middle East & North Africa"], ["asia","Asia-Pacific"], ["europe_region","Europe"],
    ["americas","Americas"], ["africa","Africa"],
  ]},
];

export const ALL_INTERESTS = INTEREST_CATEGORIES.flatMap((c) => c.items.map(([tag]) => tag));
