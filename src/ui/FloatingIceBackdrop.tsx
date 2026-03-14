import './FloatingIceBackdrop.css';

/**
 * Rotating ice blocks only in peripheral bands (corners / edges) so the
 * main column stays clean for text. pointer-events: none, behind content.
 */
export default function FloatingIceBackdrop() {
  return (
    <div className="shell-ice-backdrop" aria-hidden>
      {[
        'shell-ice-a1',
        'shell-ice-a2',
        'shell-ice-a3',
        'shell-ice-a4',
        'shell-ice-a5',
        'shell-ice-a6',
        'shell-ice-a7',
        'shell-ice-a8',
        'shell-ice-a9',
        'shell-ice-a10',
        'shell-ice-a11',
        'shell-ice-a12',
      ].map((cls) => (
        <div key={cls} className={`shell-ice-block ${cls}`} />
      ))}
    </div>
  );
}
