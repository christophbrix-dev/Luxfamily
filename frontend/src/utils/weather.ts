// Open-Meteo: free, no API key required. Used for the Luxembourg City forecast widget.
const LUX_LAT = 49.6116;
const LUX_LON = 6.1319;

export type WeatherSnapshot = {
  temperature: number;
  weatherCode: number;
  isDay: boolean;
};

export const WEATHER_DESCRIPTIONS: Record<number, { en: string; de: string; fr: string; icon: string }> = {
  0: { en: "Clear", de: "Klar", fr: "Clair", icon: "sunny-outline" },
  1: { en: "Mostly clear", de: "Heiter", fr: "Plutot clair", icon: "partly-sunny-outline" },
  2: { en: "Partly cloudy", de: "Teils bewoelkt", fr: "Partiellement nuageux", icon: "partly-sunny-outline" },
  3: { en: "Cloudy", de: "Bewoelkt", fr: "Nuageux", icon: "cloud-outline" },
  45: { en: "Foggy", de: "Neblig", fr: "Brumeux", icon: "cloudy-outline" },
  48: { en: "Foggy", de: "Neblig", fr: "Brumeux", icon: "cloudy-outline" },
  51: { en: "Drizzle", de: "Nieselregen", fr: "Bruine", icon: "rainy-outline" },
  61: { en: "Rain", de: "Regen", fr: "Pluie", icon: "rainy-outline" },
  63: { en: "Rain", de: "Regen", fr: "Pluie", icon: "rainy-outline" },
  65: { en: "Heavy rain", de: "Starker Regen", fr: "Forte pluie", icon: "rainy-outline" },
  71: { en: "Snow", de: "Schnee", fr: "Neige", icon: "snow-outline" },
  80: { en: "Showers", de: "Schauer", fr: "Averses", icon: "rainy-outline" },
  95: { en: "Thunderstorm", de: "Gewitter", fr: "Orage", icon: "thunderstorm-outline" },
};

export async function fetchLuxembourgWeather(): Promise<WeatherSnapshot | null> {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${LUX_LAT}&longitude=${LUX_LON}&current=temperature_2m,weather_code,is_day&timezone=Europe%2FLuxembourg`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const json = await res.json();
    const c = json?.current;
    if (!c) return null;
    return {
      temperature: Math.round(c.temperature_2m),
      weatherCode: c.weather_code,
      isDay: c.is_day === 1,
    };
  } catch {
    return null;
  }
}
