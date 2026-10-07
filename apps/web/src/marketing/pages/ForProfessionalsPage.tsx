import {
  forProfessionalsMeta,
  prosClosing,
  prosFaq,
  prosFaqItems,
  prosHero,
  prosHow,
  prosPledges,
  prosWho,
} from '@/marketing/content/pages/forProfessionals';
import { pageMetadata } from '@/marketing/lib/seo';
import { Board } from '@/marketing/sections/home/Board/Board';
import { Built } from '@/marketing/sections/home/Built/Built';
import { Closing } from '@/marketing/sections/pages/Closing';
import { Who } from '@/marketing/sections/pages/Who';
import { PageHero } from '@/marketing/sections/services/PageHero/PageHero';
import { Faq } from '@/marketing/sections/shared/Faq/Faq';

export const forProfessionalsMetadata = pageMetadata({ ...forProfessionalsMeta, path: '/for-professionals' });

/**
 * For professionals: the crane hero, the listing rules, how it works from registration to an
 * inspected record, who it is for, and "Get started", which goes to the professionals host's
 * sign-in.
 */
export function ForProfessionalsPage() {
  return (
    <main id="main">
      <PageHero content={prosHero} />
      <Board content={prosPledges} />
      <div id="how-it-works">
        <Built content={prosHow} />
      </div>
      <Who content={prosWho} />
      <Faq content={prosFaq} items={prosFaqItems} />
      <Closing content={prosClosing} />
    </main>
  );
}
