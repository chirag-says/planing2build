import {
  forHomeownersMeta,
  homeownersFaq,
  homeownersHero,
  homeownersProblem,
  homeownersStart,
  homeownersTiers,
} from '@/marketing/content/pages/forHomeowners';
import { pageMetadata } from '@/marketing/lib/seo';
import { Bid } from '@/marketing/sections/home/Bid/Bid';
import { Board } from '@/marketing/sections/home/Board/Board';
import { Hero } from '@/marketing/sections/home/Hero/Hero';
import { Tiers } from '@/marketing/sections/pages/Tiers';
import { Faq } from '@/marketing/sections/shared/Faq/Faq';

export const forHomeownersMetadata = pageMetadata({ ...forHomeownersMeta, path: '/for-homeowners' });

/**
 * For homeowners: introduction, the problem, free versus the package, questions, and the request
 * card that starts the journey. Every
 * section is a home page section with its own copy, so the motion is the site's own.
 */
export function ForHomeownersPage() {
  return (
    <main id="main">
      <Hero content={homeownersHero} art={null} />
      <Board content={homeownersProblem} />
      <Tiers content={homeownersTiers} />
      <Faq content={homeownersFaq} />
      <Bid content={homeownersStart} />
    </main>
  );
}
