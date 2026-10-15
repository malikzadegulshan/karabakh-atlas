// CSV import helpers for the admin panel's "Import from CSV" (admin.js):
// a small RFC 4180 parser and the mapping from spreadsheet columns to the
// fields POST /regions/<id>/cities/import expects. Pure functions with no
// DOM access, so they can be exercised on their own. The server applies
// the real validation; this only turns a file into rows.

// Columns the importer understands, in the order the template lists them.
const CSV_TEMPLATE_COLUMNS = [
  "name", "latitude", "longitude", "category", "description",
  "name_az", "name_tr", "name_ru",
  "description_az", "description_tr", "description_ru",
  "phone", "website", "image_url", "image_credit", "alt_names",
];

const CSV_MAX_ROWS = 300;

// Header spellings people are likely to use, folded onto the real names.
const CSV_HEADER_ALIASES = {
  lat: "latitude",
  lng: "longitude",
  lon: "longitude",
  long: "longitude",
  title: "name",
  type: "category",
  photo: "image_url",
  image: "image_url",
  photo_credit: "image_credit",
  site: "website",
  url: "website",
  telephone: "phone",
};

// Excel in Azerbaijani/Turkish/Russian locales saves "CSV" with
// semicolons (the comma is the decimal mark there), so the delimiter is
// detected from the header line instead of assumed.
function detectCsvDelimiter(text) {
  const counts = { ",": 0, ";": 0, "\t": 0 };
  let inQuotes = false;
  for (const ch of text) {
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (!inQuotes) {
      if (ch === "\n" || ch === "\r") {
        break;
      }
      if (ch in counts) {
        counts[ch] += 1;
      }
    }
  }
  // Ties keep the order below, so a header with none of them is a comma
  // file (e.g. a single column).
  const best = [",", ";", "\t"].reduce(
    (top, d) => (counts[d] > counts[top] ? d : top), ",");
  return counts[best] > 0 ? best : ",";
}

// Returns an array of records (arrays of strings). Handles quoted fields,
// doubled quotes, delimiters and line breaks inside quotes, \r\n / \n / \r
// endings and a leading UTF-8 byte-order mark; fully blank lines are
// dropped.
function parseCsv(text) {
  if (text.charCodeAt(0) === 0xfeff) {
    text = text.slice(1);
  }
  const delimiter = detectCsvDelimiter(text);
  const records = [];
  let record = [];
  let field = "";
  let inQuotes = false;

  function endField() {
    record.push(field);
    field = "";
  }
  function endRecord() {
    endField();
    if (record.some((value) => value.trim() !== "")) {
      records.push(record);
    }
    record = [];
  }

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"' && field === "") {
      inQuotes = true;
    } else if (ch === delimiter) {
      endField();
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") {
        i += 1;
      }
      endRecord();
    } else {
      field += ch;
    }
  }
  if (field !== "" || record.length > 0) {
    endRecord();
  }
  return records;
}

function normalizeCsvHeader(header) {
  const key = header.trim().toLowerCase().replace(/[\s-]+/g, "_");
  return CSV_HEADER_ALIASES[key] || key;
}

// "Fire station", "fire-station" and "fire_station" are all fire_station;
// labels in any of the app's languages work too ("Xəstəxana" → hospital).
function csvCategoryLookup(translations) {
  const lookup = {};
  const fold = (value) => value.trim().toLowerCase().replace(/[\s-]+/g, "_");
  (typeof CITY_CATEGORY_VALUES !== "undefined" ? CITY_CATEGORY_VALUES : [])
    .forEach((value) => { lookup[fold(value)] = value; });
  Object.values(translations || {}).forEach((lang) => {
    Object.entries(lang.categories || {}).forEach(([value, label]) => {
      lookup[fold(label)] = value;
    });
  });
  return { fold, lookup };
}

// "39,8288" (decimal comma) becomes 39.8288. Anything that still isn't a
// number is sent as the original text so the server's own message
// ("latitude must be a number") names the problem in the preview.
function parseCsvNumber(value) {
  const text = value.trim().replace(/^(-?\d+),(\d+)$/, "$1.$2");
  const number = Number(text);
  return text !== "" && Number.isFinite(number) ? number : value.trim();
}

// records: output of parseCsv (first record is the header).
// Returns { places, ignoredColumns, error } — error is a { key, ... }
// object the UI translates, or null.
function csvRecordsToPlaces(records, translations) {
  if (records.length === 0) {
    return { places: [], ignoredColumns: [], error: { key: "empty" } };
  }
  const headers = records[0].map(normalizeCsvHeader);
  const missing = ["name", "latitude", "longitude"].filter(
    (column) => !headers.includes(column));
  if (missing.length > 0) {
    return { places: [], ignoredColumns: [], error: { key: "missingColumns", columns: missing } };
  }
  const dataRecords = records.slice(1);
  if (dataRecords.length === 0) {
    return { places: [], ignoredColumns: [], error: { key: "empty" } };
  }
  if (dataRecords.length > CSV_MAX_ROWS) {
    return {
      places: [], ignoredColumns: [],
      error: { key: "tooManyRows", count: dataRecords.length, max: CSV_MAX_ROWS },
    };
  }

  const known = new Set(CSV_TEMPLATE_COLUMNS);
  const ignoredColumns = records[0]
    .filter((header, i) => header.trim() !== "" && !known.has(headers[i]));
  const { fold, lookup } = csvCategoryLookup(translations);

  const places = dataRecords.map((record) => {
    const cell = {};
    headers.forEach((header, i) => {
      const value = (record[i] || "").trim();
      if (known.has(header) && value !== "") {
        cell[header] = value;
      }
    });
    const place = { name: cell.name || "" };
    if ("latitude" in cell) { place.latitude = parseCsvNumber(cell.latitude); }
    if ("longitude" in cell) { place.longitude = parseCsvNumber(cell.longitude); }
    if (cell.category) {
      place.category = lookup[fold(cell.category)] || cell.category;
    }
    ["description", "alt_names", "phone", "website", "image_url", "image_credit"]
      .forEach((field) => { if (cell[field]) { place[field] = cell[field]; } });
    ["az", "tr", "ru"].forEach((lang) => {
      if (cell[`name_${lang}`]) {
        place.name_i18n = place.name_i18n || {};
        place.name_i18n[lang] = cell[`name_${lang}`];
      }
      if (cell[`description_${lang}`]) {
        place.description_i18n = place.description_i18n || {};
        place.description_i18n[lang] = cell[`description_${lang}`];
      }
    });
    return place;
  });
  return { places, ignoredColumns, error: null };
}

// Quote a value for CSV output only if it needs it.
function csvEscape(value) {
  return /[",\n\r;]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

function csvTemplateText() {
  const rows = [
    CSV_TEMPLATE_COLUMNS,
    ["Sample City (delete this row)", "39.8288", "46.7661", "city",
      "A short description, commas are fine", "Nümunə Şəhər", "Örnek Şehir",
      "Пример города", "", "", "", "", "", "", "", ""],
    ["Sample Hospital (delete this row)", "39.6", "47.14", "hospital",
      "", "", "", "", "", "", "", "+994 12 000 00 00",
      "https://example.com", "", "", ""],
  ];
  // The byte-order mark makes Excel open the file as UTF-8, so az/tr/ru
  // letters survive.
  return "﻿" + rows.map((row) => row.map(csvEscape).join(",")).join("\r\n") + "\r\n";
}
