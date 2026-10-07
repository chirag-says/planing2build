import {
  forHomeownersMeta,
  homeownersChecks,
  homeownersFaq,
  homeownersHero,
  homeownersHow,
  homeownersProblem,
  homeownersSolution,
  homeownersStart,
  homeownersTiers,
} from '@/marketing/content/pages/forHomeowners';
import { pageMetadata } from '@/marketing/lib/seo';
import { Bid } from '@/marketing/sections/home/Bid/Bid';
import { Board } from '@/marketing/sections/home/Board/Board';
import { Built } from '@/marketing/sections/home/Built/Built';
import { Hero } from '@/marketing/sections/home/Hero/Hero';
import { Safety } from '@/marketing/sections/home/Safety/Safety';
import { Tiers } from '@/marketing/sections/pages/Tiers';
import { Faq } from '@/marketing/sections/shared/Faq/Faq';
import { Trades } from '@/marketing/sections/shared/Trades/Trades';

export const forHomeownersMetadata = pageMetadata({ ...forHomeownersMeta, path: '/for-homeowners' });

/**
 * For homeowners: introduction, the problem, the solution, how Plan2Build solves it, free versus
 * the package, the six checks, questions, and the request card that starts the journey. Every
 * section is a home page section with its own copy, so the motion is the site's own.
 */
export function ForHomeownersPage() {
  return (
    <main id="main">
      <Hero content={homeownersHero} />
      <Board content={homeownersProblem} />
      <Trades content={homeownersSolution} />
      <Built content={homeownersHow} />
      <Tiers content={homeownersTiers} />
      <Safety content={homeownersChecks} />
      <Faq content={homeownersFaq} />
      <Bid content={homeownersStart} />
    </main>
  );
}
