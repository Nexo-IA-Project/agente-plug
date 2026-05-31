export interface ParsedUA {
  browser: string;
  os: string;
  device: "desktop" | "mobile" | "tablet";
}

export function parseUserAgent(ua: string | null | undefined): ParsedUA {
  if (!ua) return { browser: "—", os: "—", device: "desktop" };

  const browser =
    /Edg\//.test(ua) ? "Edge" :
    /OPR\/|Opera/.test(ua) ? "Opera" :
    /Chrome\//.test(ua) ? "Chrome" :
    /Firefox\//.test(ua) ? "Firefox" :
    /Safari\//.test(ua) ? "Safari" :
    "—";

  const os =
    /Windows NT/.test(ua) ? "Windows" :
    /Mac OS X/.test(ua) && !/iPhone|iPad/.test(ua) ? "macOS" :
    /Android/.test(ua) ? "Android" :
    /iPhone/.test(ua) ? "iOS" :
    /iPad/.test(ua) ? "iPadOS" :
    /Linux/.test(ua) ? "Linux" :
    "—";

  const device: ParsedUA["device"] =
    /iPad/.test(ua) ? "tablet" :
    /Mobile|Android|iPhone/.test(ua) ? "mobile" :
    "desktop";

  return { browser, os, device };
}
