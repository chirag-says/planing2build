import { projects } from '@/marketing/content/projects';
import { header } from '@/marketing/content/sections/header';
import { services } from '@/marketing/content/services';
import { site } from '@/marketing/content/site';
import { telHref } from '@/marketing/lib/text';
import { toHeaderProject, toHeaderService } from './header/data';
import { SiteHeader } from './header/SiteHeader';

/** The drawer lists at most six services. */
const MAX_SERVICES = 6;

/**
 * Site header. Rendered by the root layout straight into <body>, so the fixed bar needs no portal;
 * only the fields the header shows are sent to the client.
 */
export function Header() {
  return (
    <SiteHeader
      copy={header}
      siteName={site.name || 'Plan2Build'}
      phone={site.phone}
      phoneHref={site.phone ? telHref(site.phone) : '/contact'}
      bidHref={site.bidHref}
      projectsHref={site.projectsHref}
      projects={projects.filter((project) => project.name).slice(0, 4).map(toHeaderProject)}
      services={services.filter((service) => service.name.trim()).slice(0, MAX_SERVICES).map(toHeaderService)}
    />
  );
}
