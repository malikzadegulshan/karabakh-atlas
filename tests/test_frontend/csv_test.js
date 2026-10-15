// Run by tests/test_frontend/test_csv.py: exercises frontend/csv.js (the
// admin CSV import parser/mapper) in a bare VM context.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.join(__dirname, '..', '..', 'frontend') + path.sep;
// i18n.js declares `const TRANSLATIONS`; CITY_CATEGORY_VALUES comes from admin.js's header.
const adminHead = fs.readFileSync(root + 'admin.js', 'utf8').match(/const CITY_CATEGORY_VALUES = \[[\s\S]*?\];/)[0];
const ctx = {};
vm.createContext(ctx);
vm.runInContext(adminHead + '\n' + fs.readFileSync(root + 'i18n.js', 'utf8') + '\n' + fs.readFileSync(root + 'csv.js', 'utf8') +
  '\nthis.api = { parseCsv, csvRecordsToPlaces, csvTemplateText, detectCsvDelimiter, TRANSLATIONS, CSV_MAX_ROWS };', ctx);
const { parseCsv, csvRecordsToPlaces, csvTemplateText, TRANSLATIONS } = ctx.api;
let failed = 0;
const eq = (name, got, want) => {
  const norm = (v) => JSON.stringify(v, (k, val) => (val && typeof val === 'object' && !Array.isArray(val) ? Object.fromEntries(Object.entries(val).sort()) : val));
  const ok = norm(got) === norm(want);
  if (!ok) { failed++; console.log('FAIL', name, '\n  got ', JSON.stringify(got), '\n  want', JSON.stringify(want)); } else console.log('ok  ', name);
};
const places = (text) => csvRecordsToPlaces(parseCsv(text), TRANSLATIONS);

eq('comma csv', parseCsv('a,b,c\n1,2,3\n'), [['a','b','c'],['1','2','3']]);
eq('no trailing newline', parseCsv('a,b\n1,2'), [['a','b'],['1','2']]);
eq('CRLF + blank lines', parseCsv('a,b\r\n\r\n1,2\r\n\r\n'), [['a','b'],['1','2']]);
eq('lone CR endings', parseCsv('a,b\r1,2\r'), [['a','b'],['1','2']]);
eq('BOM stripped', parseCsv('﻿name,x\nA,1'), [['name','x'],['A','1']]);
eq('quotes: comma, doubled quote, newline inside', parseCsv('n,d\nA,"x, ""y""\nz"\n'), [['n','d'],['A','x, "y"\nz']]);
eq('semicolon delimiter', parseCsv('a;b;c\n1;2;3'), [['a','b','c'],['1','2','3']]);
eq('tab delimiter', parseCsv('a\tb\n1\t2'), [['a','b'],['1','2']]);
eq('delimiter detection ignores commas inside quoted header', parseCsv('"a,b";c\n1;2'), [['a,b','c'],['1','2']]);
eq('empty fields kept', parseCsv('a,b,c\n1,,3'), [['a','b','c'],['1','','3']]);

let r = places('Name;Lat;Lng;Type\nShusha;39,76;46,75;Fire station\nAghdam;39.99;46.93;city');
eq('semicolon + decimal comma + aliases + label category', r.places, [
  { name: 'Shusha', latitude: 39.76, longitude: 46.75, category: 'fire_station' },
  { name: 'Aghdam', latitude: 39.99, longitude: 46.93, category: 'city' }]);
r = places('name,latitude,longitude,category\nA,1,2,Xəstəxana\nB,1,2,hospital\nC,1,2,Больница\nD,1,2,spaceship');
eq('categories: az label, key, ru label, unknown passes through for the server to reject',
  r.places.map((p) => p.category), ['hospital', 'hospital', 'hospital', 'spaceship']);

r = places('name,latitude,longitude,name_az,name_ru,description_tr,phone,website\nKhankendi,39.8,46.7,Xankəndi,Ханкенди,Şehir,+994 1,https://e.com');
eq('i18n + optional fields', r.places[0], {
  name: 'Khankendi', latitude: 39.8, longitude: 46.7, name_i18n: { az: 'Xankəndi', ru: 'Ханкенди' },
  description_i18n: { tr: 'Şehir' }, phone: '+994 1', website: 'https://e.com' });
r = places('name,latitude,longitude,description\nA,x,2,\n');
eq('non-numeric latitude is sent as text for the server to reject, blank description omitted', r.places, [{ name: 'A', latitude: 'x', longitude: 2 }]);
r = places('name,latitude,longitude,colour,notes\nA,1,2,red,hi');
eq('unknown columns are reported', r.ignoredColumns, ['colour', 'notes']);
eq('missing required columns', places('name,category\nA,city').error, { key: 'missingColumns', columns: ['latitude', 'longitude'] });
eq('empty file', places('').error, { key: 'empty' });
eq('header only', places('name,latitude,longitude\n').error, { key: 'empty' });
const big = 'name,latitude,longitude\n' + Array.from({ length: 301 }, (_, i) => `P${i},1,2`).join('\n');
eq('too many rows', places(big).error, { key: 'tooManyRows', count: 301, max: 300 });
eq('exactly the maximum is fine', places(big.split('\n').slice(0, 301).join('\n')).error, null);

const t = places(csvTemplateText());
eq('template round-trips: BOM, quoting and all', [t.error, t.places.length, t.places[0].description, t.places[0].name_i18n, t.places[1].category, t.places[1].website],
  [null, 2, 'A short description, commas are fine', { az: 'Nümunə Şəhər', tr: 'Örnek Şehir', ru: 'Пример города' }, 'hospital', 'https://example.com']);
eq('template starts with a BOM', csvTemplateText().charCodeAt(0), 0xfeff);
console.log(failed ? `\n${failed} FAILED` : '\nall passed');
process.exit(failed ? 1 : 0);
