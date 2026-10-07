'use client';

import type { FinishLevel } from '@p2b/contracts';
import { useEffect, useState } from 'react';
import { browserApi } from '@/lib/api/browser';

/** The estimate the API returns for the sheet's three answers, in rupees and months. */
export type ApiEstimate = { low: number; high: number; months: number; isDemo: boolean };

/** Answers settle this long before the API is asked, so dragging the slider sends one request. */
const SETTLE_MS = 300;
/** The public estimator covers the POC city (IHB_FLOW J02); the sheet says so in its note. */
const CITY = 'Raipur';

/**
 * The public estimator (`POST /api/v1/public/estimate`) for the home cost sheet. The figures come
 * from the API's rate card, never from the browser; until the first answer arrives, and if the
 * API cannot answer, the result is null and the sheet shows a placeholder.
 */
export function useApiEstimate(floors: number, area: number, finish: FinishLevel): ApiEstimate | null {
  const [estimate, setEstimate] = useState<ApiEstimate | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const { data } = await browserApi.POST('/api/v1/public/estimate', {
          body: { city: CITY, built_up_area_sqft: Math.round(area), floors, finish_level: finish },
          signal: controller.signal,
        });
        if (data) {
          setEstimate({
            low: Number(data.total_low),
            high: Number(data.total_high),
            months: data.duration_months,
            isDemo: data.rate_card.is_demo,
          });
        }
      } catch {
        // Aborted by a newer answer, or the API is unreachable: keep what is shown.
      }
    }, SETTLE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [floors, area, finish]);

  return estimate;
}
