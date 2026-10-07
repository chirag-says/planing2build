import type { CrewContent } from '@/marketing/content/sections/crew';
import { site } from '@/marketing/content/site';
import { team } from '@/marketing/content/team';
import { CrewSection } from './CrewSection';

/** "The crew": the site-ID badges. */
export function Crew({ content }: { content: CrewContent }) {
  const members = team.map(({ slug, name, role, years, certs, quote, phone, email, badge, photo }) => ({
    slug, name, role, years, certs, quote, phone, email, badge, photo,
  }));
  return <CrewSection content={content} team={members} siteName={site.name} />;
}
