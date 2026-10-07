import type { BuiltContent } from '@/marketing/content/sections/built';
import { site } from '@/marketing/content/site';
import { BuiltSection } from './BuiltSection';
import { toBuiltProjects } from './model';
import './built.css';

/** Home page section 03: the seven stages, one per scroll, in a pinned, scroll-driven showcase. */
export function Built({ content }: { content: BuiltContent }) {
  return (
    <BuiltSection
      content={content}
      projects={toBuiltProjects(content)}
      heading={content.title.trim() || `Built by ${site.name}`}
      projectsHref={site.projectsHref}
    />
  );
}
