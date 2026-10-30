import { mkdir, writeFile } from 'node:fs/promises';
import { City, State } from 'country-state-city';

const countryCode = 'IN';
const states = State.getStatesOfCountry(countryCode)
  .map(state => ({
    name: state.name,
    code: state.isoCode,
    cities: City.getCitiesOfState(countryCode, state.isoCode)
      .map(city => city.name)
      .filter(Boolean),
  }))
  .sort((a, b) => a.name.localeCompare(b.name, 'en'));

for (const state of states) {
  state.cities = [...new Set(state.cities)].sort((a, b) => a.localeCompare(b, 'en'));
}

await mkdir(new URL('../src/data/', import.meta.url), { recursive: true });
await writeFile(
  new URL('../src/data/indiaLocations.json', import.meta.url),
  `${JSON.stringify(states)}\n`,
  'utf8',
);
console.log(`Exported ${states.length} Indian states/UTs and ${states.reduce((total, state) => total + state.cities.length, 0)} city entries.`);
