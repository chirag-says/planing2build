import { reviews } from '@/marketing/content/reviews';
import type { OwnersContent } from '@/marketing/content/sections/owners';
import { OwnersSection } from './OwnersSection';

/** "Three quotes, one house": the quote carousel with its audit sheet. */
export function Owners({ content }: { content: OwnersContent }) {
  return <OwnersSection content={content} reviews={reviews} />;
}
