import { addons } from '@/marketing/content/addons';
import type { OwnersContent } from '@/marketing/content/sections/owners';
import { OwnersSection } from './OwnersSection';

/** "After handover": the add-on services, one per slide, with the service sheet. */
export function Owners({ content }: { content: OwnersContent }) {
  return <OwnersSection content={content} reviews={addons} />;
}
