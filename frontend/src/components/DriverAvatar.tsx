import { useEffect, useState } from 'react';
import { api } from '../api/client';

const portraitCache = new Map<string, string | null>();
const inflightRequests = new Map<string, Promise<string | null>>();

function loadPortrait(reference: string): Promise<string | null> {
  if (portraitCache.has(reference)) {
    return Promise.resolve(portraitCache.get(reference) ?? null);
  }
  const existing = inflightRequests.get(reference);
  if (existing) return existing;

  const req = api
    .getPortrait(reference)
    .then((res) => {
      portraitCache.set(reference, res.thumbnail_url ?? null);
      inflightRequests.delete(reference);
      return res.thumbnail_url ?? null;
    })
    .catch(() => {
      portraitCache.set(reference, null);
      inflightRequests.delete(reference);
      return null;
    });

  inflightRequests.set(reference, req);
  return req;
}

interface DriverAvatarProps {
  reference: string;
  name: string;
  abbreviation?: string | null;
  teamColor?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

const SIZE_CLASSES: Record<NonNullable<DriverAvatarProps['size']>, string> = {
  xs: 'h-7 w-7 text-[10px]',
  sm: 'h-9 w-9 text-xs',
  md: 'h-12 w-12 text-sm',
  lg: 'h-16 w-16 text-lg',
  xl: 'h-24 w-24 text-2xl',
};

export function DriverAvatar({
  reference,
  name,
  abbreviation,
  teamColor = '#E10600',
  size = 'md',
  className = '',
}: DriverAvatarProps) {
  const [url, setUrl] = useState<string | null>(() =>
    portraitCache.has(reference) ? (portraitCache.get(reference) ?? null) : null
  );
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setImgFailed(false);
    if (portraitCache.has(reference)) {
      setUrl(portraitCache.get(reference) ?? null);
      return;
    }
    loadPortrait(reference).then((resolved) => {
      if (active) setUrl(resolved);
    });
    return () => {
      active = false;
    };
  }, [reference]);

  const initials =
    abbreviation ||
    name
      .split(' ')
      .filter(Boolean)
      .slice(-2)
      .map((p) => p[0])
      .join('')
      .toUpperCase();

  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded-full bg-[#161B26] flex items-center justify-center font-black tracking-tight text-slate-200 select-none ${SIZE_CLASSES[size]} ${className}`}
      style={{
        boxShadow: `0 0 0 2px ${teamColor || '#E10600'}`,
      }}
      title={name}
    >
      {url && !imgFailed ? (
        <img
          src={url}
          alt={name}
          loading="lazy"
          onError={() => setImgFailed(true)}
          className="h-full w-full object-cover object-top"
        />
      ) : (
        <div
          className="flex h-full w-full items-center justify-center"
          style={{
            background: `radial-gradient(circle at 30% 25%, ${teamColor}33, #0E121B 75%)`,
          }}
        >
          <span>{initials}</span>
        </div>
      )}
    </div>
  );
}
