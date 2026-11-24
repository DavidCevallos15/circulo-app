import { ArrowDownToLine, Check, Download, ExternalLink, LockKeyhole, ShieldCheck, Sparkles } from 'lucide-react';
import { PUBLIC_LINKS } from './runtime';

type WebUpgradePanelProps = {
  selectedCount: number;
  platformName: string;
  onExportSelected: () => void;
};

/**
 * Panel lateral mostrado en modo Analizador Web público (GitHub Pages / estático).
 * Explica las garantías locales y enlaza a la reserva de Círculo Pro y descarga para Windows.
 */
export default function WebUpgradePanel({
  selectedCount,
  platformName,
  onExportSelected,
}: WebUpgradePanelProps) {
  return (
    <aside className="runner-panel web-upgrade-panel" aria-label="Automatización local para Windows">
      <div className="runner-title">
        <span className="runner-symbol">
          <LockKeyhole size={18} />
        </span>
        <h2>Ejecutor en Windows</h2>
        <span className="connection-dot connected" />
      </div>

      <p className="web-panel-lead">
        Esta versión web audita tus archivos y genera reportes <strong>100% en tu navegador</strong>, sin subir datos a
        ningún servidor.
      </p>

      <div className="web-panel-badge">
        <ShieldCheck size={15} />
        <span>Sin contraseñas · procesamiento en memoria</span>
      </div>

      <div className="runner-divider" />

      <p className="field-label">¿Quieres limpiar tu cola en segundo plano?</p>
      <ul className="web-feature-list">
        <li>
          <Check size={14} />
          <span>Inicias sesión tú mismo en tu propio navegador local.</span>
        </li>
        <li>
          <Check size={14} />
          <span>Límites diarios, pausas aleatorias y programación multi-red.</span>
        </li>
        <li>
          <Check size={14} />
          <span>Cola reanudable en SQLite y parada inmediata ante alertas.</span>
        </li>
      </ul>

      {selectedCount > 0 && (
        <div className="web-selection-callout">
          <p>
            Tienes <strong>{selectedCount}</strong> {selectedCount === 1 ? 'cuenta marcada' : 'cuentas marcadas'} en{' '}
            {platformName}. Descarga tu lista para cargarla luego en el ejecutor local.
          </p>
          <button type="button" className="button small secondary" onClick={onExportSelected}>
            <ArrowDownToLine size={14} />
            Exportar targets.json
          </button>
        </div>
      )}

      <div className="web-cta-stack">
        <a
          className="button primary run-button"
          href={PUBLIC_LINKS.downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Download size={16} />
          Descargar gratis para Windows
        </a>
        <a
          className="button secondary web-cta-secondary"
          href={PUBLIC_LINKS.proUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Sparkles size={15} />
          Reservar Círculo Pro · $9 USD
          <ExternalLink size={13} />
        </a>
      </div>

      <p className="web-panel-footnote">
        La versión de escritorio es gratuita. Círculo Pro (reserva $9 USD) suma soporte directo, actualizaciones
        prioritarias y las próximas funciones.
      </p>
    </aside>
  );
}
