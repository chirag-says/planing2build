import type { KeyboardEventHandler, PointerEventHandler, Ref } from 'react';
import type { HeaderContent } from '@/marketing/content/sections/header';
import type { StyleWithVars } from '@/marketing/lib/css';
import { TYPE } from '@/marketing/lib/typography';
import { type HeaderProject, type HeaderService } from './data';
import { Arrow } from './icons';
import { NavAnchor } from './NavAnchor';
import { framerPhoto } from '@/marketing/lib/images';

type DrawerProps = {
  ref: Ref<HTMLDivElement>;
  open: boolean;
  copy: HeaderContent;
  projects: HeaderProject[];
  services: HeaderService[];
  projectsHref: string;
  bidHref: string;
  onKeyDown: KeyboardEventHandler<HTMLDivElement>;
  onPointerEnter: PointerEventHandler<HTMLDivElement>;
  onPointerLeave: PointerEventHandler<HTMLDivElement>;
};

/** Stagger slot for the drop-in transition (40ms apart, see header.css). */
const order = (index: number): StyleWithVars => ({ '--i': index });

/** Desktop mega drawer under the bar: the four newest projects, the services, the bid card. */
export function Drawer({ ref, open, copy, projects, services, projectsHref, bidHref, ...handlers }: DrawerProps) {
  // Closed, the drawer stays in the DOM for its transition; keep its links out of the tab order.
  const tabIndex = open ? 0 : -1;
  return (
    <div ref={ref} id="header-drawer" className="header-drawer gd-lt" role="region" aria-label={copy.drawerTitle} aria-hidden={!open} {...handlers}>
      <div className="header-din">
        <div className="header-dmain">
          <div className="header-dhead">
            <p style={TYPE.mono}>
              <i aria-hidden="true" />
              {copy.drawerTitle}
            </p>
            <NavAnchor href={projectsHref} tabIndex={tabIndex} style={TYPE.mono}>
              {copy.allLabel}
              <Arrow size={12} />
            </NavAnchor>
          </div>
          <div className="header-cards">
            {projects.map((project, index) => (
              <NavAnchor key={project.slug} className="header-card" href={`/projects/${project.slug}`} tabIndex={tabIndex} style={order(index)}>
                <span className="header-ci">
                  <img {...framerPhoto(project.photo, '240px')} alt={project.name} loading="lazy" decoding="async" draggable={false} />
                  {project.status && <em style={TYPE.mono}>{project.status}</em>}
                </span>
                <span className="header-cn" style={TYPE.display}>
                  <span>{project.name}</span>
                </span>
                {project.meta && (
                  <span className="header-cm" style={TYPE.mono}>
                    {project.meta}
                  </span>
                )}
              </NavAnchor>
            ))}
          </div>
        </div>
        {services.length > 0 && (
          <div className="header-servs">
            <div className="header-dhead">
              <p style={TYPE.mono}>{copy.servicesTitle}</p>
            </div>
            <ul>
              {services.map((service, index) => (
                // Service rows start dropping in alongside the fourth project card.
                <li key={service.slug} style={order(index + 3)}>
                  <NavAnchor href={`/services/${service.slug}`} tabIndex={tabIndex}>
                    <span className="header-sn" style={TYPE.display}>
                      {service.name}
                    </span>
                    {service.from && (
                      <span className="header-sf" style={TYPE.mono}>
                        From {service.from}
                      </span>
                    )}
                  </NavAnchor>
                </li>
              ))}
            </ul>
            {copy.servicesLabel && (
              <NavAnchor className="header-sall" href={copy.servicesLink} tabIndex={tabIndex} style={TYPE.mono}>
                {copy.servicesLabel}
                <Arrow size={12} />
              </NavAnchor>
            )}
          </div>
        )}
        <NavAnchor className="header-bid" href={bidHref} tabIndex={tabIndex} style={order(8)}>
          <span className="header-bk" style={TYPE.mono}>
            <i aria-hidden="true" />
            {copy.cardKicker}
          </span>
          <span className="header-bt" style={TYPE.display}>
            {copy.cardTitle}
          </span>
          {copy.cardLine && <span className="header-bl">{copy.cardLine}</span>}
          <span className="header-bb" style={TYPE.mono}>
            {copy.cardButton}
            <span>
              <Arrow size={14} />
            </span>
          </span>
        </NavAnchor>
      </div>
    </div>
  );
}
