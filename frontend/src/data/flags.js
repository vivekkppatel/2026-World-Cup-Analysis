// Team name → ISO code for flagcdn.com images (emoji flags don't render on
// Windows, so we use <img> flags everywhere). Pure data + a URL helper; the
// <Flag> React component lives in components/ui.jsx.
export const FLAG_ISO = {
  Algeria: 'dz', Argentina: 'ar', Australia: 'au', Austria: 'at', Belgium: 'be',
  'Bosnia & Herzegovina': 'ba', Brazil: 'br', Canada: 'ca', 'Cape Verde': 'cv',
  Colombia: 'co', Croatia: 'hr', 'Curaçao': 'cw', 'Czech Republic': 'cz',
  'DR Congo': 'cd', Ecuador: 'ec', Egypt: 'eg', England: 'gb-eng', France: 'fr',
  Germany: 'de', Ghana: 'gh', Haiti: 'ht', Iran: 'ir', Iraq: 'iq',
  'Ivory Coast': 'ci', Japan: 'jp', Jordan: 'jo', Mexico: 'mx', Morocco: 'ma',
  Netherlands: 'nl', 'New Zealand': 'nz', Norway: 'no', Panama: 'pa',
  Paraguay: 'py', Portugal: 'pt', Qatar: 'qa', 'Saudi Arabia': 'sa',
  Scotland: 'gb-sct', Senegal: 'sn', 'South Africa': 'za', 'South Korea': 'kr',
  Spain: 'es', Sweden: 'se', Switzerland: 'ch', Tunisia: 'tn', Turkey: 'tr',
  'United States': 'us', Uruguay: 'uy', Uzbekistan: 'uz',
}

export function flagUrl(team, w = 40) {
  const iso = FLAG_ISO[team]
  return iso ? `https://flagcdn.com/w${w}/${iso}.png` : null
}
