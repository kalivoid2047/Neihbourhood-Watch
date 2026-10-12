import { lazy, Suspense } from 'react';
import { Spinner } from './ui';

// Leaflet is ~150 KB; keep it out of the initial bundle.
const IncidentMap = lazy(() => import('./IncidentMap'));

export default function LazyMap({ height = 420, className = '', ...props }) {
  return (
    <Suspense
      fallback={
        <div className={`glass flex items-center justify-center ${className}`} style={{ height }}>
          <Spinner className="w-8 h-8 text-cyan-300" />
        </div>
      }
    >
      <IncidentMap height={height} className={className} {...props} />
    </Suspense>
  );
}
