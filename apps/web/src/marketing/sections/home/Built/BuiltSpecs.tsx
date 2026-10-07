import { TYPE } from '@/marketing/lib/typography';
import type { BuiltProject } from './model';

type BuiltSpecsProps = {
  project: BuiltProject;
  /** Set in the pinned showcase: values re-enter (and remount) whenever the project changes. */
  swapKey?: string;
};

/** Size, contract and days on site as a ruled table, then the result on a yellow plate. */
export function BuiltSpecs({ project, swapKey }: BuiltSpecsProps) {
  const swapping = swapKey !== undefined;
  return (
    <dl className="built-specs">
      {project.specs.map((spec, index) => (
        <div key={spec.label} className="built-spec">
          <dt style={TYPE.mono}>{spec.label}</dt>
          <dd style={TYPE.display}>
            <span
              key={swapKey}
              className={swapping ? 'built-sw' : undefined}
              data-ct={spec.value}
              style={swapping ? { animationDelay: `${120 + index * 60}ms` } : undefined}
            >
              {spec.value}
            </span>
          </dd>
        </div>
      ))}
      {project.result && (
        <div className="built-spec is-res gd-lt">
          <dt style={TYPE.mono}>{project.result.label}</dt>
          <dd style={TYPE.display}>
            <span key={swapKey} className={swapping ? 'built-sw' : undefined} style={swapping ? { animationDelay: '300ms' } : undefined}>
              {project.result.value}
            </span>
          </dd>
        </div>
      )}
    </dl>
  );
}
