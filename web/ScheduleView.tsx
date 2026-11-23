import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  CalendarClock,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  CirclePause,
  Clock3,
  Facebook,
  Instagram,
  LoaderCircle,
  MonitorCog,
  Music2,
  Play,
  RotateCcw,
  ShieldAlert,
} from 'lucide-react';
import type { Platform } from './parser';

export type ActionType = 'unfollow' | 'unfriend';
export type ScheduleKind = 'once' | 'daily' | 'interval';
export type RunMode = 'simulate' | 'inspect' | 'live';

export type ScheduleConfig = {
  enabled: boolean;
  kind: ScheduleKind;
  mode: RunMode;
  runAt: string;
  dailyTime: string;
  weekdays: number[];
  intervalHours: number;
  allNetworks: boolean;
  platforms: Platform[];
  limit: number;
  dailyLimit: number;
  interval: number;
  networkPause: number;
  headless: boolean;
  windowsTask: boolean;
  nextRunAt: string;
  lastRunAt: string;
  lastStatus: string;
  lastSummary: string;
  updated: string;
};

export type ScheduledQueueSummary = {
  platform: Platform;
  account: string;
  pending: number;
  done: number;
  skipped: number;
  uncertain: number;
  demo: boolean;
  actions: ActionType[];
  attemptsToday: number;
  halted: boolean;
  haltReason: string;
  haltedAt: string;
  sessionSaved: boolean;
  included: boolean;
  eligible: boolean;
  skipReason: string;
};

export type SchedulerSnapshot = {
  config: ScheduleConfig;
  queues: ScheduledQueueSummary[];
  eligibleCount: number;
  totalPendingEligible: number;
  windowsTask: {
    supported: boolean;
    registered: boolean;
    detail: string;
  };
  serverNow: string;
};

type Props = {
  scheduler: SchedulerSnapshot | null;
  online: boolean;
  busy: boolean;
  running: boolean;
  onSave: (draft: ScheduleConfig) => Promise<boolean>;
  onToggle: (enabled: boolean) => Promise<void>;
  onRunNow: (mode: RunMode) => Promise<void>;
  onClearHalt: (platform: Platform, account: string) => Promise<void>;
  onGoToPlatform: (platform: Platform, account?: string) => void;
  onGoToConnections: () => void;
};

const PLATFORM_NAMES: Record<Platform, string> = {
  instagram: 'Instagram',
  tiktok: 'TikTok',
  facebook: 'Facebook',
};

const PLATFORM_ICONS = {
  instagram: Instagram,
  tiktok: Music2,
  facebook: Facebook,
};

const WEEKDAYS = [
  { id: 0, short: 'L', label: 'Lunes' },
  { id: 1, short: 'M', label: 'Martes' },
  { id: 2, short: 'X', label: 'Miércoles' },
  { id: 3, short: 'J', label: 'Jueves' },
  { id: 4, short: 'V', label: 'Viernes' },
  { id: 5, short: 'S', label: 'Sábado' },
  { id: 6, short: 'D', label: 'Domingo' },
];

const formatter = new Intl.NumberFormat('es');
const fmt = (n: number) => formatter.format(n);

/** Convierte una fecha ISO UTC a formato compatible con input datetime-local en la zona local del equipo. */
function isoToLocalInput(iso: string): string {
  const date = iso ? new Date(iso) : new Date(Date.now() + 60 * 60 * 1000);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Convierte un valor de datetime-local a ISO UTC. */
function localInputToIso(value: string): string {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toISOString();
}

/** Formatea una fecha UTC a texto legible en hora local española junto con tiempo restante. */
function formatLocalDateTime(iso: string): string {
  if (!iso) return 'Sin programar';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'Sin programar';
  return date.toLocaleString('es', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatCountdown(iso: string): string {
  if (!iso) return '';
  const diffMs = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(diffMs)) return '';
  if (diffMs <= 0) return 'en breve';
  const totalMinutes = Math.ceil(diffMs / 60_000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `en ${days} d ${hours} h`;
  if (hours > 0) return `en ${hours} h ${minutes} min`;
  return `en ${minutes} min`;
}

const DEFAULT_CONFIG: ScheduleConfig = {
  enabled: false,
  kind: 'daily',
  mode: 'live',
  runAt: '',
  dailyTime: '22:00',
  weekdays: [0, 1, 2, 3, 4, 5, 6],
  intervalHours: 24,
  allNetworks: true,
  platforms: ['instagram', 'tiktok', 'facebook'],
  limit: 20,
  dailyLimit: 30,
  interval: 45,
  networkPause: 30,
  headless: true,
  windowsTask: false,
  nextRunAt: '',
  lastRunAt: '',
  lastStatus: 'idle',
  lastSummary: '',
  updated: '',
};

/** Vista principal de programación automática multi-red. */
export default function ScheduleView({
  scheduler,
  online,
  busy,
  running,
  onSave,
  onToggle,
  onRunNow,
  onClearHalt,
  onGoToPlatform,
  onGoToConnections,
}: Props) {
  const serverConfig = scheduler?.config || DEFAULT_CONFIG;
  const [draft, setDraft] = useState<ScheduleConfig>(serverConfig);
  const [localRunAt, setLocalRunAt] = useState<string>(() => isoToLocalInput(serverConfig.runAt));
  const [dirty, setDirty] = useState(false);

  // Sincroniza el formulario con el servidor cuando llegan cambios confirmados o no hay ediciones pendientes.
  useEffect(() => {
    if (!scheduler) return;
    if (!dirty) {
      setDraft(scheduler.config);
      setLocalRunAt(isoToLocalInput(scheduler.config.runAt));
    }
  }, [scheduler, dirty]);

  useEffect(() => {
    if (!scheduler?.config.updated) return;
    setDirty(false);
    setDraft(scheduler.config);
    setLocalRunAt(isoToLocalInput(scheduler.config.runAt));
  }, [scheduler?.config.updated]);

  const queues = scheduler?.queues || [];
  const winTask = scheduler?.windowsTask;

  const previewEligible = useMemo(() => {
    const allowed = new Set<Platform>(draft.allNetworks ? ['instagram', 'tiktok', 'facebook'] : draft.platforms);
    return queues.filter(q => {
      if (!allowed.has(q.platform) || q.pending <= 0 || q.halted) return false;
      if (draft.mode !== 'simulate' && (q.demo || !q.sessionSaved)) return false;
      return true;
    });
  }, [queues, draft.allNetworks, draft.platforms, draft.mode]);

  const hasUnfriendQueued = useMemo(
    () => previewEligible.some(q => q.actions.includes('unfriend')),
    [previewEligible],
  );

  function updateDraft(patch: Partial<ScheduleConfig>) {
    setDirty(true);
    setDraft(prev => ({ ...prev, ...patch }));
  }

  function toggleWeekday(dayId: number) {
    setDirty(true);
    setDraft(prev => {
      const exists = prev.weekdays.includes(dayId);
      if (exists && prev.weekdays.length === 1) return prev;
      const next = exists ? prev.weekdays.filter(d => d !== dayId) : [...prev.weekdays, dayId].sort((a, b) => a - b);
      return { ...prev, weekdays: next };
    });
  }

  function togglePlatform(target: Platform) {
    setDirty(true);
    setDraft(prev => {
      const exists = prev.platforms.includes(target);
      const next = exists ? prev.platforms.filter(p => p !== target) : [...prev.platforms, target];
      return { ...prev, platforms: next };
    });
  }

  async function submitSchedule(enabled: boolean) {
    const payload: ScheduleConfig = {
      ...draft,
      enabled,
      runAt: draft.kind === 'once' || (draft.kind === 'interval' && localRunAt) ? localInputToIso(localRunAt) : '',
    };
    const saved = await onSave(payload);
    if (saved) setDirty(false);
  }

  const controlsDisabled = !online || busy || running;
  const isArmed = Boolean(serverConfig.enabled);

  return (
    <div className="schedule-view">
      <section className={`schedule-status-banner ${isArmed ? 'armed' : ''}`} aria-label="Estado de la programación">
        <div className="schedule-status-main">
          <div className="schedule-status-title">
            <span className={`schedule-dot ${isArmed ? 'active' : ''}`} />
            <h2>{isArmed ? 'Programación activa' : 'Programación desactivada'}</h2>
            {dirty && <span className="schedule-dirty-badge">Cambios sin guardar</span>}
          </div>
          <p className="schedule-status-meta">
            {isArmed && serverConfig.nextRunAt ? (
              <>
                Próxima ejecución: <strong>{formatLocalDateTime(serverConfig.nextRunAt)}</strong> ({formatCountdown(serverConfig.nextRunAt)})
              </>
            ) : (
              'Configura el horario y guarda tus colas de Instagram, TikTok o Facebook para que inicien solas.'
            )}
          </p>
          {serverConfig.lastSummary && (
            <p className="schedule-last-note">
              Último estado{serverConfig.lastRunAt ? ` (${formatLocalDateTime(serverConfig.lastRunAt)})` : ''}: {serverConfig.lastSummary}
            </p>
          )}
        </div>
        <div className="schedule-status-actions">
          {isArmed && (
            <button
              className="button small secondary"
              disabled={controlsDisabled}
              onClick={() => void onToggle(false)}
            >
              <CirclePause size={15} />
              Pausar
            </button>
          )}
          <button
            className={`button small ${draft.mode === 'live' ? 'primary live-button' : 'primary'}`}
            disabled={controlsDisabled || !previewEligible.length}
            onClick={() => void onRunNow(draft.mode)}
          >
            {busy ? <LoaderCircle size={15} className="spin" /> : <Play size={15} />}
            Ejecutar lote ahora ({previewEligible.length})
          </button>
        </div>
      </section>

      <section className="schedule-section" aria-label="Colas preparadas por red">
        <div className="section-title">
          <h2>Colas preparadas en tus redes</h2>
          <span className="schedule-meta-count">
            {fmt(previewEligible.length)} de {fmt(queues.length)} listas
          </span>
        </div>
        <p className="section-description">
          Guarda selecciones desde <strong>Conexiones</strong> en cada red con el botón «Guardar en cola». El programador las procesará una tras otra respetando los límites diarios de cada cuenta.
        </p>

        {queues.length ? (
          <div className="scheduled-queue-list">
            {queues.map(item => {
              const Icon = PLATFORM_ICONS[item.platform];
              const isUnfriend = item.actions.includes('unfriend');
              return (
                <div
                  key={`${item.platform}-${item.account}`}
                  className={`scheduled-queue-row ${item.halted ? 'halted' : item.eligible ? 'ready' : ''}`}
                >
                  <div className="scheduled-queue-identity">
                    <span className="scheduled-platform-icon">
                      <Icon size={16} />
                    </span>
                    <div>
                      <strong>
                        {PLATFORM_NAMES[item.platform]} · @{item.account}
                      </strong>
                      <small>
                        {fmt(item.pending)} {item.pending === 1 ? 'pendiente' : 'pendientes'} · {fmt(item.attemptsToday)}/{fmt(draft.dailyLimit)} intentos hoy (UTC)
                        {' · '}
                        {isUnfriend ? 'Quitar de amigos (beta)' : 'Dejar de seguir'}
                      </small>
                    </div>
                  </div>
                  <div className="scheduled-queue-state">
                    {item.halted ? (
                      <>
                        <span className="queue-readiness halted">
                          <ShieldAlert size={14} />
                          Pausada por seguridad
                        </span>
                        <button
                          className="text-button"
                          disabled={controlsDisabled}
                          onClick={() => void onClearHalt(item.platform, item.account)}
                        >
                          <RotateCcw size={13} />
                          Reanudar
                        </button>
                      </>
                    ) : !item.sessionSaved && draft.mode !== 'simulate' ? (
                      <>
                        <span className="queue-readiness warn">
                          <CircleAlert size={14} />
                          Falta sesión
                        </span>
                        <button
                          className="text-button"
                          disabled={running}
                          onClick={() => onGoToPlatform(item.platform, item.account)}
                        >
                          Iniciar sesión
                          <ArrowRight size={13} />
                        </button>
                      </>
                    ) : item.eligible ? (
                      <span className="queue-readiness ready">
                        <CircleCheck size={14} />
                        Lista
                      </span>
                    ) : (
                      <span className="queue-readiness muted">{item.skipReason || 'En espera'}</span>
                    )}
                  </div>
                  {item.halted && item.haltReason && <p className="scheduled-halt-detail">{item.haltReason}</p>}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mini-empty">
            <CalendarClock size={26} />
            <p>Aún no has guardado colas en ninguna red.</p>
            <button className="text-button" onClick={onGoToConnections}>
              Ir a Conexiones y guardar una cola
              <ArrowRight size={15} />
            </button>
          </div>
        )}
      </section>

      <section className="schedule-section" aria-label="Configuración del horario">
        <div className="section-title">
          <h2>Horario y frecuencia</h2>
        </div>

        <div className="schedule-kind-group" role="radiogroup" aria-label="Tipo de frecuencia">
          {(
            [
              { id: 'once', label: 'Una sola vez', hint: 'Fecha y hora exacta' },
              { id: 'daily', label: 'Todos los días', hint: 'Ideal para respetar límites diarios' },
              { id: 'interval', label: 'Cada N horas', hint: 'Repetición periódica' },
            ] as { id: ScheduleKind; label: string; hint: string }[]
          ).map(option => (
            <button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={draft.kind === option.id}
              className={`schedule-kind-option ${draft.kind === option.id ? 'active' : ''}`}
              disabled={controlsDisabled}
              onClick={() => updateDraft({ kind: option.id })}
            >
              <strong>{option.label}</strong>
              <span>{option.hint}</span>
            </button>
          ))}
        </div>

        {draft.kind === 'once' && (
          <div className="schedule-field-row">
            <label htmlFor="schedule-run-at">
              Fecha y hora de inicio (hora local de este equipo)
              <input
                id="schedule-run-at"
                type="datetime-local"
                value={localRunAt}
                disabled={controlsDisabled}
                onChange={e => {
                  setDirty(true);
                  setLocalRunAt(e.target.value);
                }}
              />
            </label>
          </div>
        )}

        {draft.kind === 'daily' && (
          <div className="schedule-daily-grid">
            <label htmlFor="schedule-daily-time">
              Hora diaria (24 h)
              <input
                id="schedule-daily-time"
                type="time"
                value={draft.dailyTime}
                disabled={controlsDisabled}
                onChange={e => updateDraft({ dailyTime: e.target.value })}
              />
            </label>
            <div className="weekday-field">
              <span>Días activos</span>
              <div className="weekday-pills" role="group" aria-label="Días de la semana">
                {WEEKDAYS.map(day => {
                  const selected = draft.weekdays.includes(day.id);
                  return (
                    <button
                      key={day.id}
                      type="button"
                      className={`weekday-pill ${selected ? 'active' : ''}`}
                      aria-label={day.label}
                      aria-pressed={selected}
                      disabled={controlsDisabled}
                      onClick={() => toggleWeekday(day.id)}
                    >
                      {day.short}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {draft.kind === 'interval' && (
          <div className="schedule-daily-grid">
            <label htmlFor="schedule-interval-hours">
              Repetir cada (horas)
              <input
                id="schedule-interval-hours"
                type="number"
                min={1}
                max={168}
                value={draft.intervalHours}
                disabled={controlsDisabled}
                onChange={e => updateDraft({ intervalHours: Number(e.target.value) })}
              />
            </label>
            <label htmlFor="schedule-interval-start">
              Primera ejecución (opcional)
              <input
                id="schedule-interval-start"
                type="datetime-local"
                value={localRunAt}
                disabled={controlsDisabled}
                onChange={e => {
                  setDirty(true);
                  setLocalRunAt(e.target.value);
                }}
              />
            </label>
          </div>
        )}

        <div className="schedule-networks-box">
          <label className="background-toggle">
            <input
              type="checkbox"
              checked={draft.allNetworks}
              disabled={controlsDisabled}
              onChange={e => updateDraft({ allNetworks: e.target.checked })}
            />
            <span>Incluir todas las redes con cola pendiente automáticamente</span>
          </label>
          {!draft.allNetworks && (
            <div className="network-checks" role="group" aria-label="Seleccionar redes">
              {(['instagram', 'tiktok', 'facebook'] as Platform[]).map(name => (
                <label key={name} className="network-check-chip">
                  <input
                    type="checkbox"
                    checked={draft.platforms.includes(name)}
                    disabled={controlsDisabled}
                    onChange={() => togglePlatform(name)}
                  />
                  <span>{PLATFORM_NAMES[name]}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="schedule-section" aria-label="Modo y ritmo seguro">
        <div className="section-title">
          <h2>Modo y límites seguros por red</h2>
        </div>

        <div className="schedule-mode-row">
          <div>
            <label className="field-label" htmlFor="schedule-mode">
              Modo de ejecución programada
            </label>
            <div className="mode-select">
              <select
                id="schedule-mode"
                value={draft.mode}
                disabled={controlsDisabled}
                onChange={e => updateDraft({ mode: e.target.value as RunMode })}
              >
                <option value="simulate">Simulación · sin navegador</option>
                <option value="inspect">Comprobación · sin clics</option>
                <option value="live">Ejecución real automática</option>
              </select>
              <ChevronDown size={15} />
            </div>
          </div>
          {draft.mode !== 'simulate' && (
            <label className="background-toggle schedule-headless-check">
              <input
                type="checkbox"
                checked={draft.headless}
                disabled={controlsDisabled}
                onChange={e => updateDraft({ headless: e.target.checked })}
              />
              <span>Segundo plano (sin ventana visible)</span>
            </label>
          )}
        </div>

        <div className="schedule-limits-grid">
          <label>
            Límite por sesión y red
            <input
              type="number"
              min={1}
              max={500}
              value={draft.limit}
              disabled={controlsDisabled}
              onChange={e => updateDraft({ limit: Number(e.target.value) })}
            />
            <span>cuentas por lote</span>
          </label>
          <label>
            Límite diario por red
            <input
              type="number"
              min={1}
              max={1000}
              value={draft.dailyLimit}
              disabled={controlsDisabled}
              onChange={e => updateDraft({ dailyLimit: Number(e.target.value) })}
            />
            <span>intentos · UTC</span>
          </label>
          <label>
            Espera entre perfiles
            <input
              type="number"
              min={5}
              max={3600}
              value={draft.interval}
              disabled={controlsDisabled}
              onChange={e => updateDraft({ interval: Number(e.target.value) })}
            />
            <span>segundos + jitter</span>
          </label>
          <label>
            Pausa entre redes
            <input
              type="number"
              min={5}
              max={600}
              value={draft.networkPause}
              disabled={controlsDisabled}
              onChange={e => updateDraft({ networkPause: Number(e.target.value) })}
            />
            <span>segundos al cambiar</span>
          </label>
        </div>

        {hasUnfriendQueued && draft.mode === 'live' && (
          <div className="notice warning schedule-inline-notice" role="status">
            <CircleAlert size={17} />
            <span>
              Tu cola de Facebook incluye acciones de <strong>Quitar de amigos (beta)</strong>. Cada perfil se confirmará en dos pasos y se detendrá si aparece cualquier aviso o captcha.
            </span>
          </div>
        )}
      </section>

      <section className="schedule-section" aria-label="Continuidad en Windows">
        <div className="section-title">
          <h2>Ejecución con la pestaña o app cerrada</h2>
        </div>
        <div className="schedule-continuity-box">
          <div className="continuity-line">
            <Clock3 size={16} />
            <p>
              <strong>Programador interno siempre activo:</strong> aunque cierres esta pestaña del navegador, Círculo iniciará automáticamente a la hora elegida mientras mantengas abierta la ventana local (<code>iniciar.cmd</code> o <code>Circulo.exe</code>).
            </p>
          </div>
          {winTask?.supported && (
            <div className="continuity-windows">
              <label className="background-toggle">
                <input
                  type="checkbox"
                  checked={draft.windowsTask}
                  disabled={controlsDisabled}
                  onChange={e => updateDraft({ windowsTask: e.target.checked })}
                />
                <span>
                  <MonitorCog size={15} className="inline-icon" /> Registrar también en el Programador de tareas de Windows (arranca incluso con Círculo cerrado, solo con tu sesión de Windows abierta y sin pedir permisos de administrador)
                </span>
              </label>
              <small className="windows-task-detail">{winTask.detail}</small>
            </div>
          )}
        </div>

        <div className="schedule-submit-bar">
          <button
            className="button secondary"
            disabled={controlsDisabled}
            onClick={() => void submitSchedule(false)}
          >
            Guardar como desactivada
          </button>
          <button
            className={`button primary ${draft.mode === 'live' ? 'live-button' : ''}`}
            disabled={controlsDisabled}
            onClick={() => void submitSchedule(true)}
          >
            {busy ? <LoaderCircle size={16} className="spin" /> : <CalendarClock size={16} />}
            {isArmed ? 'Actualizar programación activa' : 'Guardar y activar programación'}
          </button>
        </div>
      </section>
    </div>
  );
}
