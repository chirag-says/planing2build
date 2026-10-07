import type { Photo, Project, Service } from '@/marketing/content/types';
import { PHOTO_PLACEHOLDER } from '@/marketing/lib/images';

/** What the header shows of a project: drawer cards and the sheet's "latest" rows. */
export type HeaderProject = { slug: string; name: string; status: string; meta: string; photo: string };
export type HeaderService = { slug: string; name: string; from: string };


const photoSrc = (photo: Photo | null) => photo?.src.split('?')[0] || PHOTO_PLACEHOLDER;

export const toHeaderProject = (project: Project): HeaderProject => ({
  slug: project.slug,
  name: project.name,
  status: project.status,
  meta: [project.type, project.place].filter(Boolean).join(' · '),
  photo: photoSrc(project.photo),
});

export const toHeaderService = (service: Service): HeaderService => ({
  slug: service.slug,
  name: service.name,
  from: service.from,
});

/** Layout widths the image host is asked to fill, before snapping to its three renditions. */

