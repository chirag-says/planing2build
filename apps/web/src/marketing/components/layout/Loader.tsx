import { loader } from '@/marketing/content/sections/loader';
import { site } from '@/marketing/content/site';
import { LoaderStage } from './loader/LoaderStage';
import { prePaintScript } from './loader/prePaint';

/**
 * First-visit loader. Rendered by the root layout ahead of the page column: the inline script
 * runs before anything below it paints and decides whether the loader shows; the stage then
 * plays it once React has hydrated.
 */
export function Loader() {
  if (!loader.enabled) return null;
  const wordmark = loader.wordmark.trim() || site.name.trim() || 'Girder';
  const place = loader.place.trim() || site.area.trim();

  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: prePaintScript(loader.once) }} />
      <LoaderStage
        wordmark={wordmark}
        place={place}
        tag={loader.tag}
        statuses={loader.statuses}
        counterLabel={loader.counterLabel}
        skipLabel={loader.skipLabel}
        topLevel={loader.topLevel}
        duration={loader.duration}
        once={loader.once}
      />
    </>
  );
}
