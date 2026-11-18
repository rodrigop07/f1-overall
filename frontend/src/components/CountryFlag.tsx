import { useState } from 'react';

const ISO3_TO_ISO2: Record<string, string> = {
  ARG: 'ar',
  AUS: 'au',
  AUT: 'at',
  BEL: 'be',
  BRA: 'br',
  CAN: 'ca',
  CHE: 'ch',
  CHL: 'cl',
  CHN: 'cn',
  COL: 'co',
  CZE: 'cz',
  DEU: 'de',
  DNK: 'dk',
  ESP: 'es',
  FIN: 'fi',
  FRA: 'fr',
  GBR: 'gb',
  GER: 'de',
  HUN: 'hu',
  IDN: 'id',
  IND: 'in',
  IRL: 'ie',
  ITA: 'it',
  JPN: 'jp',
  LIE: 'li',
  LUX: 'lu',
  MCO: 'mc',
  MEX: 'mx',
  MYS: 'my',
  NLD: 'nl',
  NED: 'nl',
  NZL: 'nz',
  POL: 'pl',
  PRT: 'pt',
  POR: 'pt',
  RUS: 'ru',
  SGP: 'sg',
  SWE: 'se',
  SUI: 'ch',
  THA: 'th',
  URY: 'uy',
  USA: 'us',
  VEN: 've',
  ZAF: 'za',
  RSA: 'za',
};

const NATIONALITY_TO_ISO2: Record<string, string> = {
  Argentine: 'ar',
  Australian: 'au',
  Austrian: 'at',
  Belgian: 'be',
  Brazilian: 'br',
  British: 'gb',
  Canadian: 'ca',
  Chilean: 'cl',
  Chinese: 'cn',
  Colombian: 'co',
  Czech: 'cz',
  Danish: 'dk',
  Dutch: 'nl',
  Finnish: 'fi',
  French: 'fr',
  German: 'de',
  Hungarian: 'hu',
  Indian: 'in',
  Indonesian: 'id',
  Irish: 'ie',
  Italian: 'it',
  Japanese: 'jp',
  Malaysian: 'my',
  Mexican: 'mx',
  Monegasque: 'mc',
  'New Zealander': 'nz',
  Polish: 'pl',
  Portuguese: 'pt',
  Rhodesian: 'zw',
  Russian: 'ru',
  'South African': 'za',
  Spanish: 'es',
  Swedish: 'se',
  Swiss: 'ch',
  Thai: 'th',
  Uruguayan: 'uy',
  American: 'us',
  Venezuelan: 've',
};

const COUNTRY_NAME_TO_ISO2: Record<string, string> = {
  Australia: 'au',
  Austria: 'at',
  Azerbaijan: 'az',
  Bahrain: 'bh',
  Belgium: 'be',
  Brazil: 'br',
  Canada: 'ca',
  China: 'cn',
  France: 'fr',
  Germany: 'de',
  Hungary: 'hu',
  India: 'in',
  Italy: 'it',
  Japan: 'jp',
  Malaysia: 'my',
  Mexico: 'mx',
  Monaco: 'mc',
  Morocco: 'ma',
  Netherlands: 'nl',
  Portugal: 'pt',
  Qatar: 'qa',
  Russia: 'ru',
  'Saudi Arabia': 'sa',
  Singapore: 'sg',
  'South Africa': 'za',
  'South Korea': 'kr',
  Spain: 'es',
  Sweden: 'se',
  Switzerland: 'ch',
  Turkey: 'tr',
  UAE: 'ae',
  'United Arab Emirates': 'ae',
  UK: 'gb',
  'United Kingdom': 'gb',
  USA: 'us',
  'United States': 'us',
};

export function resolveIso2({
  countryCode,
  nationality,
  country,
}: {
  countryCode?: string | null;
  nationality?: string | null;
  country?: string | null;
}): string | null {
  if (countryCode) {
    const clean = countryCode.trim().toUpperCase();
    if (clean.length === 2) return clean.toLowerCase();
    if (ISO3_TO_ISO2[clean]) return ISO3_TO_ISO2[clean];
  }
  if (nationality && NATIONALITY_TO_ISO2[nationality.trim()]) {
    return NATIONALITY_TO_ISO2[nationality.trim()];
  }
  if (country && COUNTRY_NAME_TO_ISO2[country.trim()]) {
    return COUNTRY_NAME_TO_ISO2[country.trim()];
  }
  return null;
}

interface CountryFlagProps {
  countryCode?: string | null;
  nationality?: string | null;
  country?: string | null;
  size?: 'xs' | 'sm' | 'md';
  showLabel?: boolean;
}

export function CountryFlag({
  countryCode,
  nationality,
  country,
  size = 'sm',
  showLabel = false,
}: CountryFlagProps) {
  const [imgError, setImgError] = useState(false);
  const iso2 = resolveIso2({ countryCode, nationality, country });
  const label = nationality || country || countryCode || '';

  const dimClass =
    size === 'xs'
      ? 'h-3 w-4'
      : size === 'md'
        ? 'h-4.5 w-6'
        : 'h-3.5 w-5';

  return (
    <span className="inline-flex items-center gap-1.5 align-middle" title={label}>
      {iso2 && !imgError ? (
        <img
          src={`https://flagcdn.com/w40/${iso2}.png`}
          alt={label || iso2.toUpperCase()}
          loading="lazy"
          onError={() => setImgError(true)}
          className={`${dimClass} rounded-[2px] object-cover ring-1 ring-white/15 shrink-0`}
        />
      ) : (
        <span className="inline-flex items-center justify-center rounded bg-white/10 px-1 py-0.5 font-mono text-[9px] font-bold uppercase text-slate-300">
          {countryCode || iso2?.toUpperCase() || 'F1'}
        </span>
      )}
      {showLabel && label && <span className="truncate">{label}</span>}
    </span>
  );
}
