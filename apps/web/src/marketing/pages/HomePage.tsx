import { bid } from '@/marketing/content/sections/bid';
import { board } from '@/marketing/content/sections/board';
import { budget } from '@/marketing/content/sections/budget';
import { built } from '@/marketing/content/sections/built';
import { crew } from '@/marketing/content/sections/crew';
import { faq } from '@/marketing/content/sections/faq';
import { hero } from '@/marketing/content/sections/hero';
import { owners } from '@/marketing/content/sections/owners';
import { safety } from '@/marketing/content/sections/safety';
import { schedule } from '@/marketing/content/sections/schedule';
import { trades } from '@/marketing/content/sections/trades';
import { pageMetadata } from '@/marketing/lib/seo';
import { Bid } from '@/marketing/sections/home/Bid/Bid';
import { Board } from '@/marketing/sections/home/Board/Board';
import { Built } from '@/marketing/sections/home/Built/Built';
import { Crew } from '@/marketing/sections/home/Crew/Crew';
import { Hero } from '@/marketing/sections/home/Hero/Hero';
import { Owners } from '@/marketing/sections/home/Owners/Owners';
import { Safety } from '@/marketing/sections/home/Safety/Safety';
import { Budget } from '@/marketing/sections/shared/Budget/Budget';
import { Faq } from '@/marketing/sections/shared/Faq/Faq';
import { Schedule } from '@/marketing/sections/shared/Schedule/Schedule';
import { Trades } from '@/marketing/sections/shared/Trades/Trades';

export const homeMetadata = pageMetadata({
  title: 'Plan2Build — Build With Clarity, Not Guesswork',
  description:
    "Plan2Build is India's home construction platform: plan your home, understand the real cost, compare contractors on the same scope, and keep every construction decision verified in one place.",
  path: '/',
});

export function HomePage() {
  return (
    <main id="main">
      <Hero content={hero} />
      <Board content={board} />
      <Trades content={trades} />
      <Built content={built} />
      <Schedule content={schedule} />
      <Safety content={safety} />
      <Crew content={crew} />
      <Owners content={owners} />
      <Budget content={budget} />
      <Bid content={bid} />
      <Faq content={faq} />
    </main>
  );
}
