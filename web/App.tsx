import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDownToLine,
  ArrowRight,
  CalendarClock,
  Check,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  CirclePause,
  ExternalLink,
  Facebook,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  History,
  Instagram,
  ListFilter,
  ListPlus,
  LoaderCircle,
  LockKeyhole,
  Music2,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Settings2,
  ShieldCheck,
  Trash2,
  Upload,
  Users,
  X,
} from 'lucide-react';
import {
  blankLists,
  demoLists,
  mergeFiles,
  parseExportSections,
  type Lists,
  type Person,
  type Platform,
  type Relation,
} from './parser';
import { buildCsvReport, buildHtmlReport, buildReportSummary, getFanPeople } from './reports';
import { PLATFORM_GUIDES } from './guides';
import { extractExportEntries } from './zip';
import { APP_VERSION, PUBLIC_LINKS, detectPublicWebMode } from './runtime';
import WebUpgradePanel from './WebUpgradePanel';
import ScheduleView, {
  type ActionType,
  type RunMode,
  type ScheduleConfig,
  type SchedulerSnapshot,
} from './ScheduleView';
import {
  createInitialAccountsByPlatform,
  createInitialDemoByPlatform,
  createInitialListsByPlatform,
  createInitialProtectedByPlatform,
  createInitialSelectedByPlatform,
  saveAccount,
  saveProtected,
  saveSessionLists,
} from './storage';

type UpdateInfo = {
  checkedAt: string | null;
  currentVersion: string;
  latestVersion: string | null;
  updateAvailable: boolean;
  releaseUrl: string | null;
  downloadUrl: string | null;
  sha256: string | null;
  notes: string;
  publishedAt: string | null;
  source: string | null;
  error: string | null;
};

type RunnerState = {
  token: string;
  version?: string;
  phase: string;
  mode: string | null;
  platform: Platform | null;
  account: string;
  current: string;
  processed: number;
  total: number;
  message: string;
  sessionOpen: boolean;
  syncProvider?: string | null;
  batchIndex?: number;
  batchTotal?: number;
  batchSource?: string;
  scheduler?: SchedulerSnapshot;
  update?: UpdateInfo | null;
  events: { id: number; at: string; level: string; message: string }[];
  counts: Record<string, number>;
};

type QueueRow = {
  id: number;
  platform: Platform;
  account: string;
  username: string;
  status: string;
  detail: string;
  demo?: number;
  action?: ActionType;
};

type Tab = 'connections' | 'schedule' | 'activity' | 'guide';
type FilterMode = 'not-following' | 'all' | 'mutual' | 'fans' | 'protected';
type QueueFilterMode = 'pending' | 'done' | 'skipped' | 'uncertain' | 'all';
type DisplayPerson = Person & { kind: 'following' | 'fan' };
type PendingConfirmation =
  | { kind: 'single'; reuseQueue: boolean }
  | { kind: 'schedule-save'; draft: ScheduleConfig }
  | { kind: 'schedule-run-now'; mode: RunMode };

const MAX_TEXT_FILE_BYTES = 25_000_000;
const MAX_ZIP_FILE_BYTES = 500_000_000;
const platformNames: Record<Platform, string> = { instagram: 'Instagram', tiktok: 'TikTok', facebook: 'Facebook' };
const platformIcons = { instagram: Instagram, tiktok: Music2, facebook: Facebook };
const formatter = new Intl.NumberFormat('es');
const fmt = (n: number) => formatter.format(n);
const statusNames: Record<string, string> = {
  pending: 'Pendiente',
  acting: 'En curso',
  done: 'Completado',
  skipped: 'Omitida',
  uncertain: 'Revisar manualmente',
};

function download(name: string, body: string, type = 'application/json;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 500);
}

export default function App() {
  const webMode = useMemo(() => detectPublicWebMode(), []);
  const [platform, setPlatform] = useState<Platform>('instagram');
  const [tab, setTab] = useState<Tab>('connections');
  const [listsByPlatform, setListsByPlatform] = useState<Record<Platform, Lists>>(createInitialListsByPlatform);
  const [demoByPlatform, setDemoByPlatform] = useState<Record<Platform, boolean>>(createInitialDemoByPlatform);
  const [selectedByPlatform, setSelectedByPlatform] = useState<Record<Platform, Set<string>>>(createInitialSelectedByPlatform);
  const [protectedByPlatform, setProtectedByPlatform] = useState<Record<Platform, Set<string>>>(createInitialProtectedByPlatform);
  const [accountsByPlatform, setAccountsByPlatform] = useState<Record<Platform, string>>(createInitialAccountsByPlatform);

  const [filter, setFilter] = useState<FilterMode>('not-following');
  const [queueFilter, setQueueFilter] = useState<QueueFilterMode>('pending');
  const [hideCompletedInLists, setHideCompletedInLists] = useState(true);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [importRelation, setImportRelation] = useState<Relation>('following');
  const [importing, setImporting] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState<{ text: string; error: boolean } | null>(null);

  const [limit, setLimit] = useState(20);
  const [dailyLimit, setDailyLimit] = useState(30);
  const [interval, setIntervalSeconds] = useState(45);
  const [mode, setMode] = useState<RunMode>('simulate');
  const [facebookAction, setFacebookAction] = useState<ActionType>('unfollow');
  const [headless, setHeadless] = useState(true);
  const [sessionSaved, setSessionSaved] = useState(false);
  const [confirmDeleteSession, setConfirmDeleteSession] = useState(false);

  const [runner, setRunner] = useState<RunnerState | null>(null);
  const [queue, setQueue] = useState<QueueRow[]>([]);
  const [online, setOnline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [dismissedUpdateVersion, setDismissedUpdateVersion] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<PendingConfirmation | null>(null);
  const [confirmedText, setConfirmedText] = useState('');
  const [resumeConfirmed, setResumeConfirmed] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const lastFocused = useRef<HTMLElement | null>(null);
  const token = useRef('');

  const lists = listsByPlatform[platform];
  const demo = demoByPlatform[platform];
  const selected = selectedByPlatform[platform];
  const protectedUsers = protectedByPlatform[platform];
  const account = accountsByPlatform[platform];
  const busyRunner = runner?.phase === 'running' || runner?.sessionOpen || busy;
  const displayVersion = runner?.version || APP_VERSION;

  // Sincronización periódica del ejecutor local y la cola SQLite (se omite en modo analizador web estático).
  useEffect(() => {
    if (webMode) return;
    let active = true;
    async function poll() {
      try {
        const [stateResponse, queueResponse] = await Promise.all([fetch('/api/status'), fetch('/api/queue')]);
        if (!stateResponse.ok || !queueResponse.ok) throw Error();
        const state: RunnerState = await stateResponse.json();
        const rows = await queueResponse.json();
        if (active) {
          token.current = state.token;
          setRunner(state);
          if (state.update) setUpdateInfo(state.update);
          setQueue(rows);
          setOnline(true);
        }
      } catch {
        if (active) setOnline(false);
      }
    }
    void poll();
    const timer = window.setInterval(() => void poll(), 1400);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [webMode]);

  // Comprueba si ya existe un perfil de Chromium guardado para esta red y cuenta.
  useEffect(() => {
    if (webMode) return;
    let active = true;
    setConfirmDeleteSession(false);
    const trimmed = account.trim().replace(/^@/, '');
    if (!online || !trimmed) {
      setSessionSaved(false);
      return;
    }
    async function checkSession() {
      try {
        const params = new URLSearchParams({ platform, account: trimmed });
        const response = await fetch(`/api/session?${params.toString()}`);
        if (!response.ok) return;
        const payload = await response.json();
        if (active) setSessionSaved(Boolean(payload.saved));
      } catch {
        if (active) setSessionSaved(false);
      }
    }
    void checkSession();
    return () => {
      active = false;
    };
  }, [webMode, online, platform, account, runner?.sessionOpen]);

  useEffect(() => {
    saveAccount(platform, account);
  }, [account, platform]);

  useEffect(() => {
    saveProtected(platform, protectedUsers);
  }, [protectedUsers, platform]);

  useEffect(() => {
    saveSessionLists(platform, lists, demo);
  }, [platform, lists, demo]);

  useEffect(() => {
    setPage(0);
  }, [query, filter, lists, platform]);

  useEffect(() => {
    if (!confirmation) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setConfirmation(null);
        return;
      }
      if (event.key !== 'Tab') return;
      const controls = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex="0"]',
        ) || [],
      );
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || !dialogRef.current?.contains(document.activeElement))) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialogRef.current?.contains(document.activeElement))) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      lastFocused.current?.focus();
    };
  }, [confirmation]);

  const normalizedAccount = account.trim().replace(/^@/, '').toLowerCase();
  const currentQueue = queue.filter(r => r.platform === platform && r.account === normalizedAccount);
  const pending = currentQueue.filter(r => r.status === 'pending').length;
  const completedCount = currentQueue.filter(r => r.status === 'done').length;
  const skippedCount = currentQueue.filter(r => r.status === 'skipped').length;
  const uncertainCount = currentQueue.filter(r => r.status === 'uncertain').length;
  const finishedCount = completedCount + skippedCount;
  const finishedUsernames = useMemo(
    () => new Set(currentQueue.filter(r => r.status === 'done' || r.status === 'skipped').map(r => r.username)),
    [currentQueue],
  );
  const visibleQueueRows = useMemo(
    () => (queueFilter === 'all' ? currentQueue : currentQueue.filter(r => r.status === queueFilter)),
    [currentQueue, queueFilter],
  );

  const followingPeople = useMemo<DisplayPerson[]>(
    () =>
      [...lists.following.values()]
        .filter(p => !(hideCompletedInLists && finishedUsernames.has(p.username)))
        .map(p => ({ ...p, kind: 'following' as const })),
    [lists, hideCompletedInLists, finishedUsernames],
  );
  const hiddenFinishedInListCount = useMemo(
    () => [...lists.following.values()].filter(p => finishedUsernames.has(p.username)).length,
    [lists, finishedUsernames],
  );
  const fanPeople = useMemo<DisplayPerson[]>(
    () => getFanPeople(lists, platform).map(p => ({ ...p, kind: 'fan' as const })),
    [lists, platform],
  );

  const notFollowing = followingPeople.filter(p => p.followsYou === false).length;
  const mutual = followingPeople.filter(p => p.followsYou === true).length;

  const filtered = useMemo<DisplayPerson[]>(() => {
    const cleanQuery = query.toLowerCase().replace(/^@/, '');
    const source = filter === 'fans' ? fanPeople : followingPeople;
    return source.filter(p => {
      if (cleanQuery && !p.username.includes(cleanQuery)) return false;
      if (filter === 'fans') return true;
      if (filter === 'protected') return protectedUsers.has(p.username);
      if (filter === 'not-following') return p.followsYou === false;
      if (filter === 'mutual') return p.followsYou === true;
      return true;
    });
  }, [followingPeople, fanPeople, query, filter, protectedUsers]);

  const visible = filtered.slice(page * 10, (page + 1) * 10);
  const eligibleFiltered = filtered.filter(p => p.kind === 'following' && !protectedUsers.has(p.username));
  const selectedPeople = followingPeople.filter(p => selected.has(p.username) && !protectedUsers.has(p.username));
  const selectedTargets = selectedPeople.map(({ username, profileUrl, followsYou }) => ({
    username,
    profileUrl,
    followsYou,
  }));
  const canResumeQueue = selectedPeople.length === 0 && pending > 0;
  const effectiveTargetCount = selectedPeople.length > 0 ? selectedPeople.length : pending;
  const pendingHasDemo = currentQueue.some(r => r.status === 'pending' && Boolean(r.demo));
  const pendingHasUnfriend = currentQueue.some(r => r.status === 'pending' && r.action === 'unfriend');
  const currentAction: ActionType = platform === 'facebook' ? facebookAction : 'unfollow';
  const effectiveAction: ActionType = canResumeQueue && pendingHasUnfriend ? 'unfriend' : currentAction;
  const scheduler = runner?.scheduler || null;
  const scheduleArmed = Boolean(scheduler?.config.enabled);

  const hasData = followingPeople.length > 0 || fanPeople.length > 0 || hiddenFinishedInListCount > 0;
  const activeGuide = PLATFORM_GUIDES[platform];
  const PlatformIcon = platformIcons[platform];

  function notify(text: string, error = false) {
    setNotice({ text, error });
  }

  function updatePlatformLists(targetPlatform: Platform, nextLists: Lists, isDemo: boolean) {
    setListsByPlatform(prev => ({ ...prev, [targetPlatform]: nextLists }));
    setDemoByPlatform(prev => ({ ...prev, [targetPlatform]: isDemo }));
  }

  function updatePlatformSelected(targetPlatform: Platform, updater: (prev: Set<string>) => Set<string>) {
    setSelectedByPlatform(prev => ({ ...prev, [targetPlatform]: updater(prev[targetPlatform]) }));
  }

  function updatePlatformProtected(targetPlatform: Platform, updater: (prev: Set<string>) => Set<string>) {
    setProtectedByPlatform(prev => ({ ...prev, [targetPlatform]: updater(prev[targetPlatform]) }));
  }

  function setAccountForPlatform(value: string) {
    setAccountsByPlatform(prev => ({ ...prev, [platform]: value }));
  }

  async function api(path: string, body: object) {
    const response = await fetch(`/api/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Circulo-Token': token.current },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw Error(payload.error || 'No se pudo completar la acción.');
    return payload;
  }

  async function act(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Ocurrió un error.', true);
    } finally {
      setBusy(false);
    }
  }

  function changePlatform(next: Platform) {
    if (next === platform) return;
    setPlatform(next);
    setFilter('not-following');
    setQuery('');
    setNotice(null);
    setConfirmDeleteSession(false);
  }

  async function importFiles(files: FileList | File[]) {
    if (!files.length) return;
    setImporting(true);
    try {
      let importedZip = false;
      let extractedFilesCount = 0;
      const parsedEntries: { name: string; relation: Relation; people: Person[]; demo: boolean }[] = [];

      for (const file of Array.from(files)) {
        if (file.name.toLowerCase().endsWith('.zip')) {
          if (file.size > MAX_ZIP_FILE_BYTES) {
            throw Error(`${file.name}: el ZIP supera 500 MB. Exporta solo seguidores y seguidos.`);
          }
          importedZip = true;
          const entries = await extractExportEntries(file, platform);
          if (!entries.length) {
            throw Error(
              `${file.name}: no se encontraron listas de ${platformNames[platform]} dentro del ZIP. Comprueba que pediste formato JSON (no HTML).`,
            );
          }
          for (const entry of entries) {
            try {
              const sections = parseExportSections(entry.text, entry.name, platform, importRelation);
              for (const section of sections) {
                parsedEntries.push({ name: entry.name, ...section });
              }
              extractedFilesCount += 1;
            } catch {
              // Ignora archivos secundarios del ZIP que no correspondan a listas válidas.
            }
          }
          if (!extractedFilesCount) {
            throw Error(`${file.name}: ningún archivo dentro del ZIP contenía usuarios válidos de ${platformNames[platform]}.`);
          }
        } else {
          if (file.size > MAX_TEXT_FILE_BYTES) {
            throw Error(`${file.name}: el archivo supera 25 MB. Usa listas separadas.`);
          }
          const sections = parseExportSections(await file.text(), file.name, platform, importRelation);
          for (const section of sections) {
            parsedEntries.push({ name: file.name, ...section });
          }
        }
      }

      const base = demo ? blankLists() : lists;
      const merged = mergeFiles(base, parsedEntries);
      const isDemoImport = parsedEntries.some(p => p.demo);
      updatePlatformLists(platform, merged, isDemoImport);
      updatePlatformSelected(platform, () => new Set());

      if (importedZip) {
        notify(
          `ZIP procesado en memoria: ${extractedFilesCount} archivo${extractedFilesCount > 1 ? 's' : ''} de ${platformNames[platform]} cargado${extractedFilesCount > 1 ? 's' : ''}.`,
        );
      } else {
        const count = files.length;
        notify(`${count} archivo${count > 1 ? 's' : ''} importado${count > 1 ? 's' : ''}. Los datos se procesaron en tu navegador.`);
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : 'No se pudo leer el archivo.', true);
    } finally {
      setImporting(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  function clearCurrentImport() {
    updatePlatformLists(platform, blankLists(), false);
    updatePlatformSelected(platform, () => new Set());
  }

  function toggle(username: string) {
    updatePlatformSelected(platform, prev => {
      const next = new Set(prev);
      next.has(username) ? next.delete(username) : next.add(username);
      return next;
    });
  }

  function toggleProtect(username: string) {
    updatePlatformProtected(platform, prev => {
      const next = new Set(prev);
      next.has(username) ? next.delete(username) : next.add(username);
      return next;
    });
    updatePlatformSelected(platform, prev => {
      const next = new Set(prev);
      next.delete(username);
      return next;
    });
  }

  function selectFiltered() {
    const all = eligibleFiltered.length > 0 && eligibleFiltered.every(p => selected.has(p.username));
    updatePlatformSelected(platform, prev => {
      const next = new Set(prev);
      eligibleFiltered.forEach(p => (all ? next.delete(p.username) : next.add(p.username)));
      return next;
    });
  }

  function downloadReport(format: 'csv' | 'html') {
    const summary = buildReportSummary(lists, platform, account, protectedUsers, selected);
    const stamp = new Date().toISOString().slice(0, 10);
    if (format === 'csv') {
      download(`circulo-reporte-${platform}-${stamp}.csv`, buildCsvReport(summary), 'text/csv;charset=utf-8');
      notify('Reporte CSV descargado (listo para Excel o Google Sheets).');
      return;
    }
    download(`circulo-reporte-${platform}-${stamp}.html`, buildHtmlReport(summary), 'text/html;charset=utf-8');
    notify('Reporte visual HTML descargado. Ábrelo en tu navegador o imprímelo como PDF.');
  }

  async function clearFinishedQueue() {
    await act(async () => {
      const payload = await api('queue/clear-finished', { platform, account });
      if (payload.scheduler) {
        setRunner(prev => (prev ? { ...prev, scheduler: payload.scheduler } : prev));
      }
      const removed = Number(payload.removed || 0);
      setQueueFilter('pending');
      notify(
        removed > 0
          ? `Cola actualizada: se quitaron ${fmt(removed)} cuentas terminadas. Quedan ${fmt(pending)} pendientes.`
          : 'No había cuentas terminadas por limpiar.',
      );
    });
  }

  async function deleteSavedSession() {
    await act(async () => {
      await api('session/delete', { platform, account });
      setSessionSaved(false);
      setConfirmDeleteSession(false);
      notify(`Sesión local de @${normalizedAccount} borrada de este equipo. Tu cola se conserva.`);
    });
  }

  async function saveSelectedToQueue() {
    if (!account.trim()) {
      notify('Escribe el usuario de tu cuenta en el panel de ejecución antes de guardar la cola.', true);
      return;
    }
    if (!selectedTargets.length) {
      notify('Selecciona al menos una cuenta para guardarla en cola.', true);
      return;
    }
    await act(async () => {
      const payload = await api('queue', {
        platform,
        account,
        targets: selectedTargets,
        demo,
        action: currentAction,
      });
      if (payload.scheduler) {
        setRunner(prev => (prev ? { ...prev, scheduler: payload.scheduler } : prev));
      }
      const count = Number(payload.count || selectedTargets.length);
      const actionLabel = currentAction === 'unfriend' ? 'quitar de amigos' : 'dejar de seguir';
      notify(
        `Se guardaron ${fmt(count)} cuentas en la cola de ${platformNames[platform]} (@${normalizedAccount}) para ${actionLabel}. Ya puedes incluirla en Programación.`,
      );
    });
  }

  async function saveScheduleNow(draft: ScheduleConfig) {
    let ok = false;
    await act(async () => {
      const payload = await api('schedule', draft);
      if (payload.scheduler) {
        setRunner(prev => (prev ? { ...prev, scheduler: payload.scheduler } : prev));
      }
      setConfirmation(null);
      notify(
        draft.enabled
          ? 'Programación automática guardada y activada.'
          : 'Configuración de programación guardada como desactivada.',
      );
      ok = true;
    });
    return ok;
  }

  async function handleScheduleSave(draft: ScheduleConfig): Promise<boolean> {
    if (draft.enabled && draft.mode === 'live') {
      lastFocused.current = document.activeElement as HTMLElement;
      setConfirmation({ kind: 'schedule-save', draft });
      setConfirmedText('');
      return false;
    }
    return await saveScheduleNow(draft);
  }

  async function handleScheduleToggle(enabled: boolean) {
    if (enabled && scheduler?.config.mode === 'live') {
      await handleScheduleSave({ ...scheduler.config, enabled: true });
      return;
    }
    await act(async () => {
      const payload = await api('schedule/toggle', { enabled });
      if (payload.scheduler) {
        setRunner(prev => (prev ? { ...prev, scheduler: payload.scheduler } : prev));
      }
      notify(enabled ? 'Programación reactivada.' : 'Programación automática en pausa.');
    });
  }

  async function runScheduledBatchNow(runMode: RunMode) {
    await act(async () => {
      await api('schedule/run-now', { mode: runMode });
      setConfirmation(null);
      setTab('activity');
      notify(
        runMode === 'simulate'
          ? 'Simulación multi-red iniciada. No se harán clics.'
          : 'Lote multi-red iniciado. Puedes pausarlo desde el panel de ejecución.',
      );
    });
  }

  async function handleScheduleRunNow(runMode: RunMode) {
    if (runMode === 'live') {
      lastFocused.current = document.activeElement as HTMLElement;
      setConfirmation({ kind: 'schedule-run-now', mode: runMode });
      setConfirmedText('');
      return;
    }
    await runScheduledBatchNow(runMode);
  }

  async function handleClearHalt(targetPlatform: Platform, targetAccount: string) {
    await act(async () => {
      const payload = await api('schedule/clear-halt', { platform: targetPlatform, account: targetAccount });
      if (payload.scheduler) {
        setRunner(prev => (prev ? { ...prev, scheduler: payload.scheduler } : prev));
      }
      notify(`Red ${platformNames[targetPlatform]} (@${targetAccount}) reactivada para la programación.`);
    });
  }

  async function run(reuseQueue = false) {
    if (((!reuseQueue && demo) || (reuseQueue && pendingHasDemo)) && mode !== 'simulate') {
      notify('Carga tus archivos reales antes de comprobar o ejecutar.', true);
      return;
    }
    if (!account.trim()) {
      notify('Escribe el usuario de tu cuenta en el panel de ejecución.', true);
      return;
    }
    if (!reuseQueue && !selectedTargets.length) {
      notify('Selecciona las cuentas que quieres procesar.', true);
      return;
    }
    if (mode === 'live') {
      lastFocused.current = document.activeElement as HTMLElement;
      setConfirmation({ kind: 'single', reuseQueue });
      setConfirmedText('');
      return;
    }
    await begin(reuseQueue);
  }

  function exportSelectedTargetsJson() {
    if (!selectedPeople.length) return;
    download(
      'targets.json',
      JSON.stringify(
        {
          version: 1,
          platform,
          action: currentAction,
          generatedAt: new Date().toISOString(),
          demo,
          targets: selectedTargets,
        },
        null,
        2,
      ),
    );
  }

  async function checkForUpdates() {
    if (webMode || !online || checkingUpdate) return;
    setCheckingUpdate(true);
    try {
      const payload = (await api('update/check', { force: true })) as { update?: UpdateInfo };
      if (payload.update) {
        setUpdateInfo(payload.update);
        setDismissedUpdateVersion(null);
        if (payload.update.error) {
          notify(`No se pudo comprobar actualizaciones: ${payload.update.error}`, true);
        } else if (payload.update.updateAvailable && payload.update.latestVersion) {
          notify(`Hay una nueva versión disponible: Círculo v${payload.update.latestVersion}.`);
        } else {
          notify(`Círculo v${payload.update.currentVersion} está al día.`);
        }
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : 'No se pudo comprobar actualizaciones.', true);
    } finally {
      setCheckingUpdate(false);
    }
  }

  async function begin(reuseQueue = false) {
    await act(async () => {
      if (!reuseQueue) await api('queue', { platform, account, targets: selectedTargets, demo, action: currentAction });
      await api('run', { platform, account, mode, limit, dailyLimit, interval, headless });
      setConfirmation(null);
      setTab('activity');
      notify(
        mode === 'simulate'
          ? 'Simulación iniciada. No se harán clics.'
          : headless
            ? 'Ejecución iniciada en segundo plano. Puedes pausarla cuando quieras.'
            : 'Ejecución iniciada. Puedes pausarla desde este panel.',
      );
    });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" inert={Boolean(confirmation)}>
        <a
          className="brand"
          href={webMode ? PUBLIC_LINKS.landingUrl : '/'}
          aria-label="Círculo, inicio"
        >
          <span className="brand-mark">
            <span />
          </span>
          Círculo<span className="version">{webMode ? 'web' : 'local'}</span>
        </a>
        <nav aria-label="Navegación principal">
          <button
            className={tab === 'connections' ? 'nav-item active' : 'nav-item'}
            aria-current={tab === 'connections' ? 'page' : undefined}
            onClick={() => setTab('connections')}
          >
            <Users size={19} />
            Conexiones
            <span className="nav-count">{followingPeople.length ? fmt(followingPeople.length) : '—'}</span>
          </button>
          {!webMode && (
            <>
              <button
                className={tab === 'schedule' ? 'nav-item active' : 'nav-item'}
                aria-current={tab === 'schedule' ? 'page' : undefined}
                onClick={() => setTab('schedule')}
              >
                <CalendarClock size={19} />
                Programación
                {scheduleArmed && <i className="activity-dot" aria-label="Activa" />}
              </button>
              <button
                className={tab === 'activity' ? 'nav-item active' : 'nav-item'}
                aria-current={tab === 'activity' ? 'page' : undefined}
                onClick={() => setTab('activity')}
              >
                <History size={19} />
                Actividad
                {runner?.phase === 'running' && <i className="activity-dot" />}
              </button>
            </>
          )}
          <button
            className={tab === 'guide' ? 'nav-item active' : 'nav-item'}
            aria-current={tab === 'guide' ? 'page' : undefined}
            onClick={() => setTab('guide')}
          >
            <CircleHelp size={19} />
            Cómo empezar
          </button>
        </nav>
        <div className="local-note sidebar-bottom">
          <ShieldCheck size={17} />
          <span>
            {webMode ? 'Tus archivos no salen de aquí.' : 'Tus datos se quedan aquí.'}
            <small>{webMode ? '100% en tu navegador · sin servidor.' : '100% local · sin contraseñas.'}</small>
          </span>
        </div>
        <div className="sidebar-footer">
          <span className={`connection-dot ${webMode || online ? 'connected' : ''}`} />
          <span>
            {webMode ? 'Analizador web privado' : online ? 'Ejecutor local conectado' : 'Ejecutor desconectado'}
          </span>
          {!webMode && online ? (
            <button
              type="button"
              className="version-update-button"
              onClick={() => void checkForUpdates()}
              disabled={checkingUpdate}
              title="Buscar actualizaciones oficiales"
              aria-label="Buscar actualizaciones"
            >
              <RefreshCw size={11} className={checkingUpdate ? 'spin' : ''} />
              <span>v{displayVersion}</span>
            </button>
          ) : (
            <span>v{displayVersion}</span>
          )}
        </div>
      </aside>

      <div className="main-shell" inert={Boolean(confirmation)}>
        <header className="topbar">
          <div className="breadcrumb">
            {webMode ? (
              <a className="topbar-landing-link" href={PUBLIC_LINKS.landingUrl}>
                Círculo
              </a>
            ) : (
              'Mi espacio'
            )}
            <span>/</span>
            <strong>
              {tab === 'connections'
                ? 'Conexiones'
                : tab === 'schedule'
                  ? 'Programación'
                  : tab === 'activity'
                    ? 'Actividad'
                    : 'Cómo empezar'}
            </strong>
          </div>
          <span className="private-label">
            <LockKeyhole size={14} /> {webMode ? 'Análisis privado en tu navegador' : 'Espacio local privado'}
          </span>
        </header>

        <main>
          <div className="page-heading">
            <div>
              <h1>
                {tab === 'connections'
                  ? 'Haz espacio en tu círculo.'
                  : tab === 'schedule'
                    ? 'Tu limpieza, a la hora que elijas.'
                    : tab === 'activity'
                      ? 'Cada paso, a la vista.'
                      : `Cómo exportar datos de ${activeGuide.name}.`}
              </h1>
              <p>
                {tab === 'connections'
                  ? 'Compara tus listas, genera reportes y decide a quién dejar de seguir.'
                  : tab === 'schedule'
                    ? 'Programa ejecuciones automáticas secuenciales para todas tus redes con pausas seguras.'
                    : tab === 'activity'
                      ? 'Consulta tu cola local y el registro de cada acción.'
                      : 'Sigue estos pasos para descargar tus listas oficiales en formato JSON.'}
              </p>
            </div>
          </div>

          {notice && (
            <div className={`notice ${notice.error ? 'error' : ''}`} role={notice.error ? 'alert' : 'status'}>
              {notice.error ? <CircleAlert size={18} /> : <CircleCheck size={18} />}
              <span>{notice.text}</span>
              <button aria-label="Cerrar aviso" onClick={() => setNotice(null)}>
                <X size={16} />
              </button>
            </div>
          )}

          {online && runner?.syncProvider && (
            <div className="notice warning" role="status">
              <CircleAlert size={18} />
              <span>
                Tu carpeta de datos está dentro de <strong>{runner.syncProvider}</strong>. No sincronices <code>data/profiles/</code> en la nube porque contiene cookies de sesión; mueve Círculo a una carpeta local o usa el ejecutable portable.
              </span>
            </div>
          )}

          {!webMode &&
            updateInfo?.updateAvailable &&
            updateInfo.latestVersion &&
            dismissedUpdateVersion !== updateInfo.latestVersion && (
              <div className="notice update-notice" role="status">
                <CircleCheck size={18} />
                <span>
                  Nueva versión disponible: <strong>Círculo v{updateInfo.latestVersion}</strong> (tienes v
                  {updateInfo.currentVersion}).{' '}
                  {updateInfo.notes ? `${updateInfo.notes.slice(0, 140)} ` : ''}
                  {updateInfo.releaseUrl && (
                    <a href={updateInfo.releaseUrl} target="_blank" rel="noopener noreferrer">
                      Ver actualización oficial
                    </a>
                  )}
                </span>
                <button
                  aria-label="Ocultar aviso de actualización"
                  onClick={() => setDismissedUpdateVersion(updateInfo.latestVersion)}
                >
                  <X size={16} />
                </button>
              </div>
            )}

          {!webMode && !online && (
            <div className="notice error" role="status">
              <CircleAlert size={18} />
              <span>
                El ejecutor local no está disponible. Abre la app con <code>iniciar.cmd</code>. Puedes seguir analizando archivos y descargando reportes.
              </span>
            </div>
          )}

          <div className="workspace">
            <section className="work-area" aria-label="Espacio de trabajo">
              {tab !== 'schedule' && (
                <div className="platform-tabs" role="tablist" aria-label="Red social">
                  {(['instagram', 'tiktok', 'facebook'] as Platform[]).map(p => {
                    const Icon = platformIcons[p];
                    const loadedCount = listsByPlatform[p].following.size;
                    return (
                      <button
                        key={p}
                        role="tab"
                        aria-selected={platform === p}
                        className={platform === p ? 'platform-tab active' : 'platform-tab'}
                        onClick={() => changePlatform(p)}
                        disabled={!!busyRunner}
                      >
                        <Icon size={18} />
                        {platformNames[p]}
                        {loadedCount > 0 ? (
                          <span className="tab-count">{fmt(loadedCount)}</span>
                        ) : (
                          p === 'facebook' && <span className="beta">beta</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {tab === 'schedule' && (
                <ScheduleView
                  scheduler={scheduler}
                  online={online}
                  busy={busy}
                  running={runner?.phase === 'running'}
                  onSave={handleScheduleSave}
                  onToggle={handleScheduleToggle}
                  onRunNow={handleScheduleRunNow}
                  onClearHalt={handleClearHalt}
                  onGoToPlatform={(targetPlatform, targetAccount) => {
                    changePlatform(targetPlatform);
                    if (targetAccount) {
                      setAccountsByPlatform(prev => ({ ...prev, [targetPlatform]: targetAccount }));
                    }
                    setTab('connections');
                  }}
                  onGoToConnections={() => setTab('connections')}
                />
              )}

              {tab === 'connections' && (
                <>
                  <section
                    className={`import-panel ${lists.files.length ? 'compact' : ''}`}
                    aria-label="Importación de listas"
                    onDragOver={e => {
                      e.preventDefault();
                      setDragging(true);
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={e => {
                      e.preventDefault();
                      setDragging(false);
                      if (!busyRunner) void importFiles(e.dataTransfer.files);
                    }}
                    data-dragging={dragging}
                  >
                    <div className="import-icon">
                      <FolderOpen size={lists.files.length ? 18 : 24} />
                    </div>
                    <div className="import-copy">
                      <h2>
                        {lists.files.length
                          ? `${lists.files.length} archivo${lists.files.length > 1 ? 's' : ''} en ${platformNames[platform]}`
                          : 'Importa tu ZIP oficial o tus listas.'}
                      </h2>
                      <p>
                        {lists.files.length
                          ? `${lists.hasFollowers ? 'Seguidores y seguidos cruzados' : 'Falta cargar tus seguidores'} · Conservado al cambiar de red`
                          : 'Arrastra el archivo .zip descargado de la red social (sin descomprimir) o archivos JSON, TXT o CSV.'}
                      </p>
                      {!lists.files.length && (
                        <div className="import-controls">
                          <label>
                            Si el archivo no indica su tipo:
                            <select
                              value={importRelation}
                              onChange={e => setImportRelation(e.target.value as Relation)}
                              disabled={!!busyRunner}
                            >
                              <option value="following">Cuentas que sigo</option>
                              <option value="followers">Mis seguidores</option>
                            </select>
                          </label>
                          <span>ZIP directo, JSON, TXT o CSV</span>
                        </div>
                      )}
                    </div>
                    <div className="import-actions">
                      <button
                        className="button small secondary"
                        disabled={importing || !!busyRunner}
                        onClick={() => inputRef.current?.click()}
                      >
                        {importing ? <LoaderCircle size={15} className="spin" /> : <Upload size={15} />}
                        {lists.files.length ? 'Añadir' : 'Elegir archivos'}
                      </button>
                      {lists.files.length > 0 && (
                        <button className="text-button muted" disabled={!!busyRunner} onClick={clearCurrentImport}>
                          Limpiar
                        </button>
                      )}
                    </div>
                  </section>

                  <input
                    ref={inputRef}
                    type="file"
                    accept=".json,.txt,.csv,.zip"
                    multiple
                    className="visually-hidden"
                    aria-label="Archivos de seguidos y seguidores"
                    onChange={e => e.target.files && void importFiles(e.target.files)}
                  />

                  {demo && (
                    <div className="demo-banner">
                      <span>
                        <span className="demo-indicator" />
                        Datos de ejemplo. Ninguna de estas cuentas es tuya.
                      </span>
                      <button onClick={clearCurrentImport}>
                        Salir del ejemplo
                        <X size={14} />
                      </button>
                    </div>
                  )}

                  <div className="stats-strip" role="group" aria-label="Resumen de relaciones">
                    <button
                      type="button"
                      className={`stat-card ${filter === 'all' ? 'active' : ''}`}
                      onClick={() => setFilter('all')}
                    >
                      <span>Siguiendo</span>
                      <strong>{fmt(followingPeople.length)}</strong>
                    </button>
                    <button
                      type="button"
                      className={`stat-card ${filter === 'not-following' ? 'active' : ''}`}
                      onClick={() => setFilter('not-following')}
                    >
                      <span>No te siguen</span>
                      <strong>{lists.hasFollowers ? fmt(notFollowing) : '—'}</strong>
                    </button>
                    <button
                      type="button"
                      className={`stat-card ${filter === 'mutual' ? 'active' : ''}`}
                      onClick={() => setFilter('mutual')}
                    >
                      <span>Mutuas</span>
                      <strong>{lists.hasFollowers ? fmt(mutual) : '—'}</strong>
                    </button>
                    <button
                      type="button"
                      className={`stat-card ${filter === 'fans' ? 'active' : ''}`}
                      onClick={() => setFilter('fans')}
                    >
                      <span>Solo te siguen</span>
                      <strong>{lists.hasFollowers ? fmt(fanPeople.length) : '—'}</strong>
                    </button>
                    <button
                      type="button"
                      className={`stat-card protected-stat ${filter === 'protected' ? 'active' : ''}`}
                      onClick={() => setFilter('protected')}
                    >
                      <ShieldCheck size={17} />
                      <span>{fmt(protectedUsers.size)} protegidas</span>
                    </button>
                  </div>

                  <div className="table-toolbar">
                    <label className="search">
                      <Search size={17} />
                      <input
                        placeholder="Buscar una cuenta…"
                        aria-label="Buscar una cuenta"
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                      />
                    </label>
                    <div className="toolbar-right">
                      {hasData && (
                        <div className="report-actions">
                          <button className="button small secondary" onClick={() => downloadReport('csv')}>
                            <FileSpreadsheet size={14} />
                            Reporte CSV
                          </button>
                          <button className="button small secondary" onClick={() => downloadReport('html')}>
                            <FileText size={14} />
                            Reporte visual
                          </button>
                        </div>
                      )}
                      <label className="filter-select">
                        <ListFilter size={16} />
                        <select
                          aria-label="Filtrar conexiones"
                          value={filter}
                          onChange={e => setFilter(e.target.value as FilterMode)}
                        >
                          <option value="not-following">No me siguen</option>
                          <option value="all">Todas las cuentas</option>
                          <option value="mutual">Conexiones mutuas</option>
                          <option value="fans">Solo te siguen</option>
                          <option value="protected">Protegidas</option>
                        </select>
                        <ChevronDown size={14} />
                      </label>
                    </div>
                  </div>

                  {followingPeople.length > 0 && !lists.hasFollowers && (
                    <p className="inline-hint">
                      Carga también tus seguidores para ver quién no te sigue de vuelta y quién solo te sigue.
                    </p>
                  )}

                  {hiddenFinishedInListCount > 0 && (
                    <div className="sync-filter-bar">
                      <span>
                        {hideCompletedInLists
                          ? `Se ocultaron ${fmt(hiddenFinishedInListCount)} cuentas ya completadas u omitidas en tu cola.`
                          : `Mostrando ${fmt(hiddenFinishedInListCount)} cuentas ya procesadas en tu cola.`}
                      </span>
                      <button
                        className="text-button"
                        onClick={() => setHideCompletedInLists(prev => !prev)}
                      >
                        {hideCompletedInLists ? 'Mostrarlas' : 'Ocultar terminadas'}
                      </button>
                    </div>
                  )}

                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th className="checkbox-cell">
                            <input
                              type="checkbox"
                              aria-label="Seleccionar todas las cuentas del filtro"
                              checked={eligibleFiltered.length > 0 && eligibleFiltered.every(p => selected.has(p.username))}
                              onChange={selectFiltered}
                              disabled={!!busyRunner || !eligibleFiltered.length}
                            />
                          </th>
                          <th>Cuenta</th>
                          <th>Relación</th>
                          <th className="protection-cell">Proteger</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visible.map((p, i) => {
                          const isFan = p.kind === 'fan';
                          return (
                            <tr key={`${p.kind}-${p.username}`} data-selected={!isFan && selected.has(p.username)}>
                              <td className="checkbox-cell">
                                <input
                                  type="checkbox"
                                  checked={!isFan && selected.has(p.username)}
                                  aria-label={`Seleccionar ${p.username}`}
                                  onChange={() => toggle(p.username)}
                                  disabled={isFan || protectedUsers.has(p.username) || !!busyRunner}
                                />
                              </td>
                              <td>
                                <a href={p.profileUrl} target="_blank" rel="noreferrer" className="account-link">
                                  <span className={`avatar avatar-${i % 5}`}>{p.username.slice(0, 2).toUpperCase()}</span>
                                  <span>
                                    <strong>@{p.username}</strong>
                                    <small>{platformNames[platform]}</small>
                                  </span>
                                  <ExternalLink size={13} />
                                </a>
                              </td>
                              <td>
                                <span
                                  className={`relation ${
                                    isFan
                                      ? 'fan'
                                      : p.followsYou === true
                                        ? 'mutual'
                                        : p.followsYou === false
                                          ? 'not-mutual'
                                          : 'unknown'
                                  }`}
                                >
                                  <i />
                                  {isFan
                                    ? 'Solo te sigue'
                                    : p.followsYou === true
                                      ? 'Te sigue'
                                      : p.followsYou === false
                                        ? 'No te sigue'
                                        : 'Sin comprobar'}
                                </span>
                              </td>
                              <td className="protection-cell">
                                <button
                                  className={`protect-button ${protectedUsers.has(p.username) ? 'protected' : ''}`}
                                  aria-label={`${protectedUsers.has(p.username) ? 'Desproteger' : 'Proteger'} ${p.username}`}
                                  aria-pressed={protectedUsers.has(p.username)}
                                  disabled={!!busyRunner}
                                  onClick={() => toggleProtect(p.username)}
                                >
                                  <ShieldCheck size={19} />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>

                    {!visible.length && (
                      <div className="empty-state">
                        <span className="empty-orbit">
                          <Users size={28} />
                        </span>
                        <h3>{hasData ? 'No hay cuentas en este filtro.' : 'Tu círculo empieza aquí.'}</h3>
                        <p>
                          {hasData
                            ? 'Prueba otro filtro o limpia la búsqueda.'
                            : 'Arrastra tu archivo ZIP oficial o tus listas para revisar quién te sigue y quién no.'}
                        </p>
                        {!hasData && (
                          <div className="empty-actions">
                            <button
                              className="text-button"
                              onClick={() => {
                                updatePlatformLists(platform, demoLists(platform), true);
                                updatePlatformSelected(platform, () => new Set());
                              }}
                            >
                              Explorar con datos de ejemplo
                              <ArrowRight size={15} />
                            </button>
                            <button className="text-button muted" onClick={() => setTab('guide')}>
                              Ver cómo descargar mis datos
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="table-footer">
                    <span>
                      {filtered.length
                        ? `${page * 10 + 1}–${Math.min((page + 1) * 10, filtered.length)} de ${fmt(filtered.length)} cuentas`
                        : 'Sin cuentas para mostrar'}
                    </span>
                    <div>
                      <button className="text-button muted" disabled={page === 0} onClick={() => setPage(page - 1)}>
                        Anterior
                      </button>
                      <button
                        className="text-button muted"
                        disabled={(page + 1) * 10 >= filtered.length}
                        onClick={() => setPage(page + 1)}
                      >
                        Siguiente
                      </button>
                    </div>
                  </div>

                  <div className="selection-bar">
                    <span>
                      <span className="selection-count">{fmt(selectedPeople.length)}</span>
                      cuentas seleccionadas
                    </span>
                    <button
                      className="text-button"
                      disabled={!selectedPeople.length || !!busyRunner}
                      onClick={() => updatePlatformSelected(platform, () => new Set())}
                    >
                      Deseleccionar
                    </button>
                    {!webMode && (
                      <button
                        className="button small secondary"
                        disabled={!selectedPeople.length || !online || !!busyRunner}
                        onClick={() => void saveSelectedToQueue()}
                      >
                        <ListPlus size={15} />
                        Guardar en cola
                      </button>
                    )}
                    <button
                      className="button small secondary"
                      disabled={!selectedPeople.length}
                      onClick={exportSelectedTargetsJson}
                    >
                      <ArrowDownToLine size={15} />
                      Exportar JSON
                    </button>
                  </div>
                </>
              )}

              {tab === 'activity' && (
                <div className="activity-view">
                  <div className="section-title">
                    <h2>Cola de {platformNames[platform]}</h2>
                    <button
                      className="text-button"
                      onClick={() => download('circulo-resultados.json', JSON.stringify(currentQueue, null, 2))}
                      disabled={!currentQueue.length}
                    >
                      <ArrowDownToLine size={15} />
                      Exportar resultados
                    </button>
                  </div>
                  <p className="section-description">
                    {account ? `Perfil local: @${account}.` : 'Escribe tu usuario en el panel de ejecución para ver su cola.'} Los pendientes se conservan al pausar o cerrar la app.
                  </p>
                  {(pending > 0 || finishedCount > 0) && (
                    <div className="activity-actions">
                      {pending > 0 && (
                        <button
                          className="button primary"
                          disabled={!!busyRunner || !online}
                          onClick={() => {
                            setResumeConfirmed(true);
                            void run(true);
                          }}
                        >
                          <RotateCcw size={16} />
                          Procesar {pending} pendientes
                        </button>
                      )}
                      {finishedCount > 0 && (
                        <button
                          className="button secondary"
                          disabled={!!busyRunner || !online}
                          onClick={() => void clearFinishedQueue()}
                        >
                          <Trash2 size={15} />
                          Limpiar terminadas ({finishedCount})
                        </button>
                      )}
                    </div>
                  )}
                  <div className="queue-filter-bar" role="group" aria-label="Filtrar cola por estado">
                    <button
                      type="button"
                      className={`queue-chip ${queueFilter === 'pending' ? 'active' : ''}`}
                      onClick={() => setQueueFilter('pending')}
                    >
                      {pending} pendientes
                    </button>
                    <button
                      type="button"
                      className={`queue-chip ${queueFilter === 'done' ? 'active' : ''}`}
                      onClick={() => setQueueFilter('done')}
                    >
                      {completedCount} completadas
                    </button>
                    {skippedCount > 0 && (
                      <button
                        type="button"
                        className={`queue-chip ${queueFilter === 'skipped' ? 'active' : ''}`}
                        onClick={() => setQueueFilter('skipped')}
                      >
                        {skippedCount} omitidas
                      </button>
                    )}
                    <button
                      type="button"
                      className={`queue-chip ${queueFilter === 'uncertain' ? 'active' : ''}`}
                      onClick={() => setQueueFilter('uncertain')}
                    >
                      {uncertainCount} por revisar
                    </button>
                    <button
                      type="button"
                      className={`queue-chip ${queueFilter === 'all' ? 'active' : ''}`}
                      onClick={() => setQueueFilter('all')}
                    >
                      Todas ({currentQueue.length})
                    </button>
                  </div>
                  {visibleQueueRows.length ? (
                    <div className="queue-list">
                      {visibleQueueRows.map(row => (
                        <div className="queue-row" key={row.id}>
                          <span>
                            @{row.username}
                            {row.action === 'unfriend' && <em className="queue-action-tag">Quitar de amigos</em>}
                          </span>
                          <span className={`queue-status ${row.status}`}>{statusNames[row.status] || row.status}</span>
                          {row.detail && <small>{row.detail}</small>}
                        </div>
                      ))}
                    </div>
                  ) : currentQueue.length ? (
                    <div className="mini-empty">
                      <CircleCheck size={24} />
                      <p>No hay cuentas en este estado.</p>
                      <button className="text-button" onClick={() => setQueueFilter(pending > 0 ? 'pending' : 'all')}>
                        {pending > 0 ? `Ver ${pending} pendientes` : 'Ver toda la cola'}
                      </button>
                    </div>
                  ) : (
                    <div className="mini-empty">
                      <History size={24} />
                      <p>Aún no hay cuentas en esta cola.</p>
                      <button className="text-button" onClick={() => setTab('connections')}>
                        Revisar conexiones
                        <ArrowRight size={15} />
                      </button>
                    </div>
                  )}
                  <div className="section-title log-heading">
                    <h2>Registro de actividad</h2>
                    <span>Últimos 60 eventos</span>
                  </div>
                  <div className="event-log">
                    {runner?.events.length ? (
                      runner.events.map(event => (
                        <div key={event.id} className={`event ${event.level}`}>
                          <time dateTime={event.at}>
                            {new Date(event.at).toLocaleTimeString('es', {
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </time>
                          <span>{event.message}</span>
                        </div>
                      ))
                    ) : (
                      <p>Las ejecuciones aparecerán aquí.</p>
                    )}
                  </div>
                </div>
              )}

              {tab === 'guide' && (
                <div className="guide-view">
                  <div className="guide-meta">
                    <span>
                      Tiempo estimado: <strong>{activeGuide.estimatedTime}</strong>
                    </span>
                    <span>
                      Archivos aceptados: <code>{activeGuide.filesHint}</code>
                    </span>
                  </div>
                  <ol>
                    {activeGuide.steps.map(step => (
                      <li key={step.title}>
                        <strong>{step.title}</strong>
                        <p>{step.detail}</p>
                      </li>
                    ))}
                  </ol>
                  <div className="guide-tip">
                    <ShieldCheck size={17} />
                    <p>{activeGuide.quickTip}</p>
                  </div>
                  <h2>Seguridad de tu sesión local</h2>
                  <p>
                    Antes de ejecutar un lote real, Círculo comprueba automáticamente que el usuario autenticado en el navegador coincide con el que escribiste. Tus cookies viven únicamente en <code>data/profiles/</code> y puedes borrarlas en cualquier momento con el botón <strong>Borrar sesión</strong>. Evita colocar la carpeta de la app dentro de OneDrive o Dropbox.
                  </p>
                  <h2>Transparencia e independencia</h2>
                  <p>
                    Círculo es software local e independiente, no afiliado ni respaldado por Meta (Instagram, Facebook) ni por TikTok. En el modo web tus archivos nunca salen de tu navegador; en el modo escritorio tú controlas tu sesión, límites y pausas.
                  </p>
                  <button className="button secondary" onClick={() => setTab('connections')}>
                    Ir a importar mis archivos
                    <ArrowRight size={15} />
                  </button>
                </div>
              )}
            </section>

            {webMode ? (
              <WebUpgradePanel
                selectedCount={selectedPeople.length}
                platformName={platformNames[platform]}
                onExportSelected={exportSelectedTargetsJson}
              />
            ) : (
            <aside className="runner-panel" aria-label="Panel de ejecución">
              <div className="runner-title">
                <span className="runner-symbol">
                  <Settings2 size={18} />
                </span>
                <h2>Ejecución</h2>
                <span className={`connection-dot ${online ? 'connected' : ''}`} />
              </div>

              <div className="account-field">
                <label htmlFor="account">Tu cuenta de {platformNames[platform]}</label>
                <div className="input-with-icon">
                  <PlatformIcon size={17} />
                  <input
                    id="account"
                    placeholder="tu.usuario"
                    value={account}
                    onChange={e => setAccountForPlatform(e.target.value)}
                    disabled={!!busyRunner}
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
              </div>

              {account.trim() && online && (
                <div className={`session-pill ${sessionSaved ? 'saved' : ''}`}>
                  {sessionSaved ? <CircleCheck size={14} /> : <CircleAlert size={14} />}
                  <span>{sessionSaved ? 'Sesión guardada · se verifica al ejecutar' : 'Sin sesión guardada aún'}</span>
                </div>
              )}

              <div className="session-actions">
                <button
                  className="button session-button"
                  disabled={!online || !account || busy || runner?.phase === 'running'}
                  onClick={() =>
                    void act(async () => {
                      await api(runner?.sessionOpen ? 'session/close' : 'session/open', { platform, account });
                      notify(
                        runner?.sessionOpen
                          ? 'Cerrando el navegador y guardando el perfil…'
                          : sessionSaved
                            ? 'Ventana abierta para comprobar tu sesión guardada. Cierra la ventana o pulsa Guardar y cerrar al terminar.'
                            : 'Inicia sesión una sola vez en la ventana que se abrirá y luego ciérrala o pulsa Guardar.',
                      );
                    })
                  }
                >
                  {runner?.sessionOpen ? <Check size={16} /> : <ExternalLink size={16} />}
                  {runner?.sessionOpen
                    ? 'Guardar y cerrar'
                    : sessionSaved
                      ? 'Revisar sesión'
                      : 'Iniciar sesión (1 vez)'}
                </button>
                {sessionSaved && !runner?.sessionOpen && online && (
                  <button
                    className="button icon-danger-button"
                    aria-label="Borrar sesión local"
                    title="Cerrar y borrar sesión local"
                    disabled={!!busyRunner}
                    onClick={() => setConfirmDeleteSession(prev => !prev)}
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>

              {confirmDeleteSession && sessionSaved && (
                <div className="inline-confirm" role="region" aria-label="Confirmar borrado de sesión">
                  <p>¿Borrar cookies locales de <strong>@{normalizedAccount}</strong>?</p>
                  <div>
                    <button className="button small secondary" onClick={() => setConfirmDeleteSession(false)} disabled={busy}>
                      Cancelar
                    </button>
                    <button className="button small danger" onClick={() => void deleteSavedSession()} disabled={busy}>
                      Borrar sesión
                    </button>
                  </div>
                </div>
              )}

              <div className="runner-divider" />

              {platform === 'facebook' && (
                <div className="facebook-action-field">
                  <label className="field-label" htmlFor="facebook-action">
                    Acción en Facebook
                  </label>
                  <div className="mode-select">
                    <select
                      id="facebook-action"
                      value={facebookAction}
                      disabled={!!busyRunner}
                      onChange={e => setFacebookAction(e.target.value as ActionType)}
                    >
                      <option value="unfollow">Dejar de seguir (Siguiendo)</option>
                      <option value="unfriend">Quitar de amigos (beta)</option>
                    </select>
                    <ChevronDown size={15} />
                  </div>
                  {facebookAction === 'unfriend' && (
                    <p className="inline-action-warning">
                      Irreversible sin nueva solicitud de amistad. Requiere URLs exactas de perfil.
                    </p>
                  )}
                </div>
              )}

              <label className="field-label" htmlFor="mode">
                Modo de ejecución
              </label>
              <div className="mode-select">
                <select
                  id="mode"
                  value={mode}
                  disabled={!!busyRunner}
                  onChange={e => setMode(e.target.value as typeof mode)}
                >
                  <option value="simulate">Simulación · sin navegador</option>
                  <option value="inspect">Comprobación · sin clics</option>
                  <option value="live">Ejecución real</option>
                </select>
                <ChevronDown size={15} />
              </div>

              {mode !== 'simulate' && (
                <label className="background-toggle">
                  <input
                    type="checkbox"
                    checked={headless}
                    onChange={e => setHeadless(e.target.checked)}
                    disabled={!!busyRunner}
                  />
                  <span>Ejecutar en segundo plano (sin ventana visible)</span>
                </label>
              )}

              <div className="limit-fields">
                <label>
                  Límite de sesión
                  <input
                    aria-label="Límite de sesión"
                    type="number"
                    min="1"
                    max="500"
                    value={limit}
                    onChange={e => setLimit(Number(e.target.value))}
                    disabled={!!busyRunner}
                  />
                  <span>cuentas</span>
                </label>
                <label>
                  Límite diario
                  <input
                    aria-label="Límite diario"
                    type="number"
                    min="1"
                    max="1000"
                    value={dailyLimit}
                    onChange={e => setDailyLimit(Number(e.target.value))}
                    disabled={!!busyRunner}
                  />
                  <span>intentos · UTC</span>
                </label>
              </div>

              <label className="interval-label" htmlFor="interval">
                Espera entre perfiles<span>{interval} s</span>
              </label>
              <input
                id="interval"
                className="interval-range"
                type="range"
                min="5"
                max="180"
                step="5"
                value={interval}
                onChange={e => setIntervalSeconds(Number(e.target.value))}
                disabled={!!busyRunner}
              />
              <div className="range-labels">
                <span>5 s</span>
                <span>180 s</span>
              </div>

              <div className="run-summary">
                <div>
                  <span>{canResumeQueue ? 'En cola pendiente' : 'Seleccionadas'}</span>
                  <strong>{fmt(effectiveTargetCount)} cuentas</strong>
                </div>
                <div>
                  <span>En esta sesión</span>
                  <strong>{fmt(Math.min(effectiveTargetCount, limit))} máx.</strong>
                </div>
              </div>

              {runner?.phase === 'running' ? (
                <button
                  className="button pause-button"
                  disabled={busy}
                  onClick={() =>
                    void act(async () => {
                      await api('pause', {});
                    })
                  }
                >
                  <CirclePause size={17} />
                  Pausar ejecución
                </button>
              ) : (
                <button
                  className={`button primary run-button ${mode === 'live' ? 'live-button' : ''}`}
                  disabled={
                    !online ||
                    !!busyRunner ||
                    !effectiveTargetCount ||
                    ((canResumeQueue ? pendingHasDemo : demo) && mode !== 'simulate')
                  }
                  onClick={() => {
                    setResumeConfirmed(canResumeQueue);
                    void run(canResumeQueue);
                  }}
                >
                  {busy ? <LoaderCircle size={17} className="spin" /> : canResumeQueue ? <RotateCcw size={16} /> : <Play size={16} />}
                  {canResumeQueue
                    ? mode === 'simulate'
                      ? `Simular ${fmt(pending)} pendientes`
                      : mode === 'inspect'
                        ? `Comprobar ${fmt(pending)} pendientes`
                        : `Continuar cola (${fmt(pending)})`
                    : mode === 'simulate'
                      ? 'Iniciar simulación'
                      : mode === 'inspect'
                        ? 'Comprobar selección'
                        : currentAction === 'unfriend'
                          ? 'Quitar de amigos selección'
                          : 'Dejar de seguir selección'}
                </button>
              )}

              {runner && runner.phase !== 'idle' && (
                <div className={`live-status ${runner.phase === 'error' ? 'error' : ''}`} role="status">
                  <div>
                    <span>
                      {runner.phase === 'running'
                        ? runner.batchTotal && runner.batchTotal > 1 && runner.platform
                          ? `Red ${runner.batchIndex}/${runner.batchTotal} · ${platformNames[runner.platform]}`
                          : 'En curso'
                        : runner.phase === 'paused'
                          ? 'En pausa'
                          : runner.phase === 'error'
                            ? 'Requiere revisión'
                            : runner.phase === 'session'
                              ? 'Sesión abierta'
                              : 'Finalizado'}
                    </span>
                    <strong>
                      {runner.processed}/{runner.total}
                    </strong>
                  </div>
                  {runner.total > 0 && (
                    <progress value={runner.processed} max={runner.total} aria-label="Progreso de ejecución" />
                  )}
                  <p>{runner.message}</p>
                </div>
              )}
            </aside>
            )}
          </div>
        </main>
      </div>

      {/* Navegación inferior ergonómica exclusiva para pantallas móviles (zona del pulgar + safe-area) */}
      <nav
        className={`mobile-bottom-nav ${webMode ? 'web-mode' : ''}`}
        aria-label="Navegación móvil"
        inert={Boolean(confirmation)}
      >
        <button
          className={tab === 'connections' ? 'mobile-nav-item active' : 'mobile-nav-item'}
          aria-current={tab === 'connections' ? 'page' : undefined}
          onClick={() => setTab('connections')}
        >
          <Users size={20} />
          <span>Conexiones</span>
        </button>
        {!webMode && (
          <>
            <button
              className={tab === 'schedule' ? 'mobile-nav-item active' : 'mobile-nav-item'}
              aria-current={tab === 'schedule' ? 'page' : undefined}
              onClick={() => setTab('schedule')}
            >
              <CalendarClock size={20} />
              <span>Programar</span>
              {scheduleArmed && <i className="mobile-dot" />}
            </button>
            <button
              className={tab === 'activity' ? 'mobile-nav-item active' : 'mobile-nav-item'}
              aria-current={tab === 'activity' ? 'page' : undefined}
              onClick={() => setTab('activity')}
            >
              <History size={20} />
              <span>Actividad</span>
              {runner?.phase === 'running' && <i className="mobile-dot" />}
            </button>
          </>
        )}
        <button
          className={tab === 'guide' ? 'mobile-nav-item active' : 'mobile-nav-item'}
          aria-current={tab === 'guide' ? 'page' : undefined}
          onClick={() => setTab('guide')}
        >
          <CircleHelp size={20} />
          <span>Guía</span>
        </button>
      </nav>

      {confirmation && (
        <div className="modal-backdrop" onClick={() => !busy && setConfirmation(null)}>
          <section
            ref={dialogRef}
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            onClick={e => e.stopPropagation()}
          >
            <button
              className="dialog-close"
              aria-label="Cerrar confirmación"
              onClick={() => setConfirmation(null)}
              disabled={busy}
            >
              <X size={20} />
            </button>
            <CircleAlert size={30} />
            {confirmation.kind === 'single' ? (
              <>
                <h2 id="confirm-title">Confirma tu selección</h2>
                <p>
                  Vas a {effectiveAction === 'unfriend' ? <strong>quitar de tus amigos</strong> : 'dejar de seguir'} hasta{' '}
                  <strong>{Math.min(resumeConfirmed ? pending : selectedPeople.length, limit)} cuentas</strong> en{' '}
                  {platformNames[platform]} con el perfil local <strong>@{account}</strong>
                  {headless ? ' en segundo plano' : ''}. Se verificará automáticamente que la sesión abierta corresponde a esa cuenta.
                </p>
                <label htmlFor="confirm-account">Escribe tu usuario para ejecutar</label>
                <input
                  id="confirm-account"
                  autoFocus
                  value={confirmedText}
                  onChange={e => setConfirmedText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Escape') setConfirmation(null);
                  }}
                  placeholder={account}
                />
                <div className="dialog-actions">
                  <button className="button secondary" onClick={() => setConfirmation(null)} disabled={busy}>
                    Cancelar
                  </button>
                  <button
                    className="button primary"
                    disabled={busy || confirmedText.trim().replace(/^@/, '').toLowerCase() !== normalizedAccount}
                    onClick={() => void begin(confirmation.reuseQueue)}
                  >
                    {busy ? <LoaderCircle className="spin" size={16} /> : <Play size={16} />}
                    Ejecutar ahora
                  </button>
                </div>
              </>
            ) : confirmation.kind === 'schedule-save' ? (
              <>
                <h2 id="confirm-title">Confirma la programación real</h2>
                <p>
                  Círculo iniciará automáticamente acciones reales en{' '}
                  <strong>
                    {confirmation.draft.allNetworks
                      ? 'todas las redes con cola pendiente'
                      : confirmation.draft.platforms.map(p => platformNames[p]).join(', ')}
                  </strong>{' '}
                  con un máximo de <strong>{fmt(confirmation.draft.limit)} cuentas</strong> por sesión y{' '}
                  <strong>{fmt(confirmation.draft.dailyLimit)} intentos diarios</strong> por cuenta. Cualquier captcha o cambio de sesión pausará esa red de inmediato.
                </p>
                <label htmlFor="confirm-schedule">Escribe PROGRAMAR para activar</label>
                <input
                  id="confirm-schedule"
                  autoFocus
                  value={confirmedText}
                  onChange={e => setConfirmedText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Escape') setConfirmation(null);
                  }}
                  placeholder="PROGRAMAR"
                />
                <div className="dialog-actions">
                  <button className="button secondary" onClick={() => setConfirmation(null)} disabled={busy}>
                    Cancelar
                  </button>
                  <button
                    className="button primary live-button"
                    disabled={busy || confirmedText.trim().toUpperCase() !== 'PROGRAMAR'}
                    onClick={() => void saveScheduleNow(confirmation.draft)}
                  >
                    {busy ? <LoaderCircle className="spin" size={16} /> : <CalendarClock size={16} />}
                    Activar programación
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2 id="confirm-title">Confirma el lote multi-red</h2>
                <p>
                  Se procesarán secuencialmente <strong>{fmt(scheduler?.eligibleCount || 0)} colas listas</strong> (
                  {fmt(scheduler?.totalPendingEligible || 0)} cuentas pendientes en total), respetando el límite por sesión y las pausas entre redes.
                </p>
                <label htmlFor="confirm-batch">Escribe EJECUTAR para iniciar ahora</label>
                <input
                  id="confirm-batch"
                  autoFocus
                  value={confirmedText}
                  onChange={e => setConfirmedText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Escape') setConfirmation(null);
                  }}
                  placeholder="EJECUTAR"
                />
                <div className="dialog-actions">
                  <button className="button secondary" onClick={() => setConfirmation(null)} disabled={busy}>
                    Cancelar
                  </button>
                  <button
                    className="button primary live-button"
                    disabled={busy || confirmedText.trim().toUpperCase() !== 'EJECUTAR'}
                    onClick={() => void runScheduledBatchNow(confirmation.mode)}
                  >
                    {busy ? <LoaderCircle className="spin" size={16} /> : <Play size={16} />}
                    Iniciar lote ahora
                  </button>
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
