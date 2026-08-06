// UI-text translations (English, Azerbaijani, Turkish, Russian).
// These are best-effort translations, not reviewed by native speakers of
// each language — sanity-check the az/tr/ru strings before relying on them.
// City data itself (names/descriptions) is unaffected by this; it stays
// in whatever language it was entered in the backend.
const TRANSLATIONS = {
  en: {
    title: "Karabakh Atlas",
    subtitle: "MVP demo — cities loaded live from the backend API.",
    loading: "Loading…",
    noCities:
      "Backend is reachable, but no cities have been added yet. " +
      "Use console.py or the API to add some.",
    citiesLoaded: (n) => `${n} cit${n === 1 ? "y" : "ies"} loaded.`,
    apiError: (base, msg) =>
      `Could not reach the API at ${base}. Is the backend running? (${msg})`,
    noInfo: "No information added for this city yet.",
    layerStreets: "Streets",
    layerSatellite: "Satellite",
    sidebarClose: "Close city list",
    sidebarOpen: "Open city list",
    sectionCities: "Cities",
    sectionRoads: "Roads",
    sectionPois: "Points of Interest",
  },
  az: {
    title: "Qarabağ Atlası",
    subtitle: "MVP demosu — şəhərlər backend API-dən canlı yüklənir.",
    loading: "Yüklənir…",
    noCities:
      "Backend əlçatandır, lakin hələ heç bir şəhər əlavə edilməyib. " +
      "Əlavə etmək üçün console.py və ya API-dən istifadə edin.",
    citiesLoaded: (n) => `${n} şəhər yükləndi.`,
    apiError: (base, msg) =>
      `${base} ünvanındakı API-yə qoşulmaq mümkün olmadı. Backend ` +
      `işləyirmi? (${msg})`,
    noInfo: "Bu şəhər üçün hələ məlumat əlavə edilməyib.",
    layerStreets: "Küçələr",
    layerSatellite: "Peyk",
    sidebarClose: "Şəhər siyahısını bağla",
    sidebarOpen: "Şəhər siyahısını aç",
    sectionCities: "Şəhərlər",
    sectionRoads: "Yollar",
    sectionPois: "Maraqlı yerlər",
  },
  tr: {
    title: "Karabağ Atlası",
    subtitle: "MVP demo — şehirler backend API'den canlı yükleniyor.",
    loading: "Yükleniyor…",
    noCities:
      "Backend erişilebilir durumda, ancak henüz şehir eklenmedi. " +
      "Eklemek için console.py veya API'yi kullanın.",
    citiesLoaded: (n) => `${n} şehir yüklendi.`,
    apiError: (base, msg) =>
      `${base} adresindeki API'ye ulaşılamadı. Backend çalışıyor mu? (${msg})`,
    noInfo: "Bu şehir için henüz bilgi eklenmedi.",
    layerStreets: "Sokaklar",
    layerSatellite: "Uydu",
    sidebarClose: "Şehir listesini kapat",
    sidebarOpen: "Şehir listesini aç",
    sectionCities: "Şehirler",
    sectionRoads: "Yollar",
    sectionPois: "İlgi Çekici Yerler",
  },
  ru: {
    title: "Атлас Карабаха",
    subtitle: "MVP-демо — города загружаются напрямую с backend API.",
    loading: "Загрузка…",
    noCities:
      "Backend доступен, но города ещё не добавлены. Используйте " +
      "console.py или API, чтобы добавить их.",
    citiesLoaded: (n) => `Загружено городов: ${n}.`,
    apiError: (base, msg) =>
      `Не удалось подключиться к API по адресу ${base}. Backend запущен? (${msg})`,
    noInfo: "Информация об этом городе пока не добавлена.",
    layerStreets: "Улицы",
    layerSatellite: "Спутник",
    sidebarClose: "Закрыть список городов",
    sidebarOpen: "Открыть список городов",
    sectionCities: "Города",
    sectionRoads: "Дороги",
    sectionPois: "Интересные места",
  },
};

const DEFAULT_LANG = "en";

function getStoredLang() {
  try {
    return localStorage.getItem("kba_lang");
  } catch (err) {
    return null;
  }
}

function setStoredLang(lang) {
  try {
    localStorage.setItem("kba_lang", lang);
  } catch (err) {
    /* localStorage unavailable (e.g. private browsing); ignore */
  }
}
