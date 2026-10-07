import { budget } from '@/marketing/content/sections/budget';
import { faq } from '@/marketing/content/sections/faq';
import { pageHero } from '@/marketing/content/sections/pageHero';
import { schedule } from '@/marketing/content/sections/schedule';
import { trades } from '@/marketing/content/sections/trades';
import { pageMetadata } from '@/marketing/lib/seo';
import { PageHero } from '@/marketing/sections/services/PageHero/PageHero';
import { Budget } from '@/marketing/sections/shared/Budget/Budget';
import { Faq } from '@/marketing/sections/shared/Faq/Faq';
import { Schedule } from '@/marketing/sections/shared/Schedule/Schedule';
import { Trades } from '@/marketing/sections/shared/Trades/Trades';

export const servicesMetadata = pageMetadata({
  title: 'Services — Plan2Build: cost check, quote review, Build Plan and independent inspections',
  description:
    'A free home cost check, independent review and comparison of contractor quotes, a Complete Build Plan, and independent inspections at the six stages that cannot be undone. We never take your contract.',
  path: '/services',
});

export function ServicesPage() {
  return (
    <main id="main">
      <PageHero content={pageHero} />
      <Trades content={trades} />
      <Schedule content={schedule} />
      <Budget content={budget} />
      <Faq content={faq} />
    </main>
  );
}
