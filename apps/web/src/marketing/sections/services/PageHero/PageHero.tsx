import type { PageHeroContent } from '@/marketing/content/sections/pageHero';
import { site } from '@/marketing/content/site';
import { PageHeroSection } from './PageHeroSection';

/** The `/services` hero: headline, buttons and the crane hoisting the promise words. */
export function PageHero({ content }: { content: PageHeroContent }) {
  const { bidHref, licence, projectsHref, proof } = site;
  return <PageHeroSection content={content} site={{ bidHref, licence, projectsHref, proof }} />;
}
