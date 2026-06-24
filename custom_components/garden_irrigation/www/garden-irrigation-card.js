/*
 * Garden Irrigation card
 * Manages multiple irrigation setups, each either "sequential" (one start time,
 * zones run in order) or "specific" (per-zone schedules). Two card modes:
 *   - view: adjust durations, set times, run/stop
 *   - edit: everything above + add/delete zones & setups, switch & script
 *           assignment, scheduling-mode toggle.
 * Plain custom element, no build step. All time fields are forced 24h.
 */

const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_SHORT = {
  en: { mon: "M", tue: "T", wed: "W", thu: "T", fri: "F", sat: "S", sun: "S" },
  pt: { mon: "S", tue: "T", wed: "Q", thu: "Q", fri: "S", sat: "S", sun: "D" },
};
const DAY_LABEL = {
  en: { mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday" },
  pt: { mon: "Segunda", tue: "Terça", wed: "Quarta", thu: "Quinta", fri: "Sexta", sat: "Sábado", sun: "Domingo" },
};

const STR = {
  en: {
    title: "Garden watering",
    edit: "Edit", done: "Done", addZone: "Add zone", addSetup: "Add setup",
    run: "Run", stop: "Stop", runSequence: "Run sequence",
    starts: "Starts", startsLabel: "Starts:", scheduling: "Scheduling:",
    sequential: "Sequential", specific: "Specific times",
    deleteSetup: "Delete setup", deleteZone: "Delete zone",
    noStartTimes: "No start times", noSchedules: "No schedules",
    schedulesLabel: "Schedules", add: "Add", duration: "Duration",
    preScript: "Pre-irrigation script", postScript: "Post-irrigation script",
    preScriptShort: "Pre-script", postScriptShort: "Post-script", switchRelay: "Switch / relay",
    scheduled: "scheduled", manual: "manual", watering: "Watering", everyDay: "every day",
    noSetupsEdit: "No setups yet. Use “Add setup” to create one (e.g. Garden, Trees).",
    noSetupsView: "No irrigation setups. Switch to edit mode to add one.",
    noZones: "No zones yet.",
    zoneName: "Zone name", zoneNamePh: "e.g. Front lawn",
    durationMinutes: "Duration (minutes)", cancel: "Cancel", saveZone: "Save zone",
    setupName: "Setup name", setupNamePh: "e.g. Trees", schedulingMode: "Scheduling mode",
    startDays: "Start time & days", createSetup: "Create setup", renameSetup: "Rename setup",
    runsNth: (n) => `runs ${ordinalEn(n)}`,
    confirmDelZone: (n) => `Delete zone “${n}”?`,
    confirmDelSetup: (n) => `Delete the whole “${n}” setup and its zones?`,
    needNameSwitch: "Enter a name and pick a switch.",
    needSetupName: "Enter a setup name.",
    entityNotReady: "Zone entity not ready yet.",
    collides: (t, l) => `Start time collides (sequence runs ${t} min): ${l}`,
    collisionWarn: (t, l) => `⚠️ Colliding start times (sequence runs ${t} min): ${l}`,
    actionFailed: (e) => `Action failed: ${e}`,
    addZoneFail: (e) => `Could not add zone: ${e}`,
    addSetupFail: (e) => `Could not add setup: ${e}`,
    updateFail: (e) => `Update failed: ${e}`,
    deleteFail: (e) => `Delete failed: ${e}`,
    addStartFail: (e) => `Could not add start time: ${e}`,
    removeStartFail: (e) => `Could not remove start time: ${e}`,
    addSchedFail: (e) => `Could not add schedule: ${e}`,
    removeSchedFail: (e) => `Could not remove schedule: ${e}`,
    skipRain: "Scheduled watering will be skipped — recent rain",
    skipForecast: "Scheduled watering will be skipped — rain forecast",
    rainSkipTitle: "Rain skip (scheduled runs)",
    rainEntity: "Rain sensor / weather",
    forecastEntity: "Weather (forecast)",
    lookback: "Look-back (h)",
    lookahead: "Look-ahead (h)",
    rainThreshold: "Rain amount (mm)",
    rainChance: "Rain chance (%)",
    rainInfoPrefix: "Skips watering if ",
    rainInfoOr: " or ",
    rainInfoRecent: (mm, h) => `it rained <b>≥${mm} mm</b> in the last <b>${h} h</b>`,
    rainInfoRecentBinary: (h) => `it rained in the last <b>${h} h</b>`,
    rainInfoForecast: (p, h) => `<b>≥${p}%</b> rain is forecast within <b>${h} h</b>`,
    enable: "Enable",
    disable: "Disable",
    skipIfRained: "Skip if it rained",
    skipIfForecast: "Skip if rain forecast",
    tabZones: "Zones",
    tabSchedule: "Schedule",
    tabScripts: "Scripts",
    tabRain: "Rain",
    specificHint: "Each zone has its own times — set them on the Zones tab.",
    scriptsHint: "Sequence scripts apply to sequential setups. Per-zone scripts are on the Zones tab.",
    history: "History",
    close: "Close",
    noHistory: "No activity yet.",
    histSequence: "Sequence started",
    histStarted: "started",
    histFinished: "finished",
    histStopped: "stopped",
    histSkipped: "Watering skipped",
    histOffFailed: "may still be open — switch didn't confirm off",
    histSkipRecent: "recent rain",
    histSkipForecast: "rain forecast",
    today: "Today",
    yesterday: "Yesterday",
    tabNotify: "Notifications",
    notifyTitle: "Notify on failures",
    notifyTarget: "Notification target",
    notifyHint: "Sends a push notification if a zone fails to start or a valve can't be confirmed closed.",
    notifyTest: "Send test",
    notifyTestSent: "Test notification sent.",
    notifyTestFail: "Could not send — pick a notification target first.",
  },
  pt: {
    title: "Rega do jardim",
    edit: "Editar", done: "Concluir", addZone: "Adicionar zona", addSetup: "Adicionar conjunto",
    run: "Regar", stop: "Parar", runSequence: "Correr sequência",
    starts: "Começa", startsLabel: "Começa:", scheduling: "Agendamento:",
    sequential: "Sequencial", specific: "Horas específicas",
    deleteSetup: "Eliminar conjunto", deleteZone: "Eliminar zona",
    noStartTimes: "Sem horas de início", noSchedules: "Sem agendamentos",
    schedulesLabel: "Agendamentos", add: "Adicionar", duration: "Duração",
    preScript: "Script de pré-rega", postScript: "Script de pós-rega",
    preScriptShort: "Script pré", postScriptShort: "Script pós", switchRelay: "Interruptor / relé",
    scheduled: "agendada", manual: "manual", watering: "A regar", everyDay: "todos os dias",
    noSetupsEdit: "Ainda não há conjuntos. Use “Adicionar conjunto” para criar um (por ex. Jardim, Árvores).",
    noSetupsView: "Sem conjuntos de rega. Mude para o modo de edição para adicionar um.",
    noZones: "Ainda não há zonas.",
    zoneName: "Nome da zona", zoneNamePh: "por ex. Relvado da frente",
    durationMinutes: "Duração (minutos)", cancel: "Cancelar", saveZone: "Guardar zona",
    setupName: "Nome do conjunto", setupNamePh: "por ex. Árvores", schedulingMode: "Modo de agendamento",
    startDays: "Hora de início e dias", createSetup: "Criar conjunto", renameSetup: "Renomear conjunto",
    runsNth: (n) => `corre ${n}.º`,
    confirmDelZone: (n) => `Eliminar a zona “${n}”?`,
    confirmDelSetup: (n) => `Eliminar todo o conjunto “${n}” e as suas zonas?`,
    needNameSwitch: "Introduza um nome e escolha um interruptor.",
    needSetupName: "Introduza um nome para o conjunto.",
    entityNotReady: "A entidade da zona ainda não está pronta.",
    collides: (t, l) => `A hora de início colide (a sequência demora ${t} min): ${l}`,
    collisionWarn: (t, l) => `⚠️ Horas de início em colisão (a sequência demora ${t} min): ${l}`,
    actionFailed: (e) => `Ação falhou: ${e}`,
    addZoneFail: (e) => `Não foi possível adicionar a zona: ${e}`,
    addSetupFail: (e) => `Não foi possível adicionar o conjunto: ${e}`,
    updateFail: (e) => `Atualização falhou: ${e}`,
    deleteFail: (e) => `Eliminação falhou: ${e}`,
    addStartFail: (e) => `Não foi possível adicionar a hora de início: ${e}`,
    removeStartFail: (e) => `Não foi possível remover a hora de início: ${e}`,
    addSchedFail: (e) => `Não foi possível adicionar o agendamento: ${e}`,
    removeSchedFail: (e) => `Não foi possível remover o agendamento: ${e}`,
    skipRain: "A rega agendada será ignorada — choveu recentemente",
    skipForecast: "A rega agendada será ignorada — previsão de chuva",
    rainSkipTitle: "Ignorar com chuva (execuções agendadas)",
    rainEntity: "Sensor de chuva / meteorologia",
    forecastEntity: "Meteorologia (previsão)",
    lookback: "Período anterior (h)",
    lookahead: "Período seguinte (h)",
    rainThreshold: "Quantidade de chuva (mm)",
    rainChance: "Probabilidade de chuva (%)",
    rainInfoPrefix: "Não rega se ",
    rainInfoOr: " ou ",
    rainInfoRecent: (mm, h) => `choveu <b>≥${mm} mm</b> nas últimas <b>${h} h</b>`,
    rainInfoRecentBinary: (h) => `choveu nas últimas <b>${h} h</b>`,
    rainInfoForecast: (p, h) => `há previsão de chuva <b>≥${p}%</b> nas próximas <b>${h} h</b>`,
    enable: "Ativar",
    disable: "Desativar",
    skipIfRained: "Ignorar se choveu",
    skipIfForecast: "Ignorar se houver previsão de chuva",
    tabZones: "Zonas",
    tabSchedule: "Agendamento",
    tabScripts: "Scripts",
    tabRain: "Chuva",
    specificHint: "Cada zona tem os seus próprios horários — defina-os no separador Zonas.",
    scriptsHint: "Os scripts da sequência aplicam-se a conjuntos sequenciais. Os scripts por zona estão no separador Zonas.",
    history: "Histórico",
    close: "Fechar",
    noHistory: "Ainda sem atividade.",
    histSequence: "Sequência iniciada",
    histStarted: "iniciou",
    histFinished: "concluída",
    histStopped: "parada",
    histSkipped: "Rega ignorada",
    histOffFailed: "pode continuar aberta — o interruptor não confirmou o fecho",
    histSkipRecent: "choveu recentemente",
    histSkipForecast: "previsão de chuva",
    today: "Hoje",
    yesterday: "Ontem",
    tabNotify: "Notificações",
    notifyTitle: "Notificar em falhas",
    notifyTarget: "Destino da notificação",
    notifyHint: "Envia uma notificação push se uma zona falhar ao iniciar ou se uma válvula não confirmar o fecho.",
    notifyTest: "Enviar teste",
    notifyTestSent: "Notificação de teste enviada.",
    notifyTestFail: "Não foi possível enviar — escolha primeiro um destino.",
  },
};

function ordinalEn(n) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

const STYLES = `
  :host { display: block; }
  ha-card { padding: 16px 18px 18px; }
  .header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }
  .header ha-icon { color: var(--primary-color); --mdc-icon-size: 26px; }
  .header h1 { font-size: 1.5rem; font-weight: 700; margin: 0; color: var(--primary-text-color); }
  .header .spacer { flex: 1; }
  select.setup-select {
    font: inherit; font-size: 1.2rem; font-weight: 700; border: none;
    background: transparent; color: var(--primary-text-color); cursor: pointer;
  }
  button {
    font: inherit; cursor: pointer; border-radius: 10px;
    border: 1px solid var(--divider-color); background: var(--card-background-color, #fff);
    color: var(--primary-text-color); padding: 8px 14px;
    display: inline-flex; align-items: center; gap: 6px;
    transition: background .15s, border-color .15s;
  }
  button:hover { background: var(--secondary-background-color); }
  button.primary { font-weight: 600; }
  button.active { border-color: var(--primary-color); color: var(--primary-color); font-weight: 600; }
  .icon-btn { border-radius: 10px; padding: 8px; line-height: 0; }
  .icon-btn ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  .icon-btn.active { border-color: var(--primary-color); }
  .icon-btn.active ha-icon { color: var(--primary-color); }
  .icon-btn.ghost { border-color: transparent; background: transparent; }
  .icon-btn.ghost:hover { background: var(--secondary-background-color); }
  .icon-btn.ghost ha-icon { --mdc-icon-size: 19px; opacity: .75; }
  .head-actions { display: flex; align-items: center; gap: 6px; }
  .toggle { display: inline-flex; border: 1px solid var(--divider-color); border-radius: 10px; overflow: hidden; }
  .toggle button { border: none; border-radius: 0; padding: 6px 12px; }
  .toggle button.on { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .setup-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 10px 0 4px; }
  .seq-bar {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    background: var(--secondary-background-color); border-radius: 12px; padding: 10px 14px; margin-top: 10px;
  }
  .seq-bar .lbl { color: var(--secondary-text-color); }
  .zone { border: 1px solid var(--divider-color); border-radius: 16px; padding: 16px 18px; margin-top: 14px; }
  .zone.running { border-color: var(--primary-color); box-shadow: 0 0 0 1px var(--primary-color); }
  .zone-head { display: flex; align-items: flex-start; gap: 10px; }
  .zone-head .titles { flex: 1; min-width: 0; }
  .zone-name { font-size: 1.15rem; font-weight: 700; color: var(--primary-text-color); display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .zone-name input { font: inherit; font-weight: 700; padding: 4px 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color,#fff); color: var(--primary-text-color); }
  .zone-sub { font-family: var(--code-font-family, monospace); color: var(--secondary-text-color); font-size: .9rem; margin-top: 4px; }
  .row { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
  .row .label { width: 86px; color: var(--primary-text-color); font-weight: 500; }
  input[type="range"] { flex: 1; accent-color: var(--primary-color); height: 4px; }
  .dur-value { font-weight: 700; min-width: 56px; text-align: right; }
  .sched-label { color: var(--primary-text-color); font-weight: 500; margin-top: 14px; }
  .chips { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; }
  .chip { display: inline-flex; align-items: center; gap: 6px; background: var(--secondary-background-color); border-radius: 999px; padding: 5px 10px; font-size: .92rem; }
  .chip ha-icon { --mdc-icon-size: 16px; color: var(--secondary-text-color); }
  .chip .x { cursor: pointer; color: var(--secondary-text-color); padding: 0 2px; }
  .chip .x:hover { color: var(--error-color); }
  .no-sched { color: var(--secondary-text-color); }
  .time24 { display: inline-flex; align-items: center; gap: 2px; border: 1px solid var(--divider-color); border-radius: 10px; padding: 3px 8px; }
  .time24 select { font: inherit; border: none; background: transparent; color: var(--primary-text-color); cursor: pointer; }
  .time24 .colon { color: var(--secondary-text-color); }
  .days { display: inline-flex; gap: 4px; }
  .day { width: 30px; height: 30px; padding: 0; justify-content: center; border-radius: 50%; color: var(--secondary-text-color); }
  .day.on { background: var(--primary-color); color: var(--text-primary-color,#fff); border-color: var(--primary-color); }
  .days-static { color: var(--primary-text-color); }
  hr { border: none; border-top: 1px solid var(--divider-color); margin: 16px 0; }
  .actions { display: flex; align-items: center; gap: 14px; }
  .status { color: var(--secondary-text-color); }
  .status b { color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
  button.stop { color: var(--error-color); border-color: var(--error-color); }
  .field-row { display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
  .field { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 180px; }
  .field label { font-size: .8rem; color: var(--secondary-text-color); }
  .form { border: 1px dashed var(--divider-color); border-radius: 14px; padding: 14px 16px; margin-top: 12px; display: grid; gap: 10px; }
  .form input[type="text"], .form input[type="number"] { font: inherit; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color,#fff); color: var(--primary-text-color); }
  .form .form-actions { display: flex; gap: 10px; justify-content: flex-end; }
  .empty { color: var(--secondary-text-color); margin-top: 12px; }

  /* ---- Edit overlay ---- */
  .overlay { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: flex-start; justify-content: center; padding: 28px 16px; overflow: auto; }
  .overlay-bg { position: fixed; inset: 0; background: rgba(0,0,0,.5); backdrop-filter: blur(1px); }
  .overlay-panel {
    position: relative; z-index: 1; margin: 0 auto;
    width: min(880px, 96vw); max-height: calc(100vh - 56px); overflow: auto;
    background: var(--ha-card-background, var(--card-background-color, #fff));
    color: var(--primary-text-color);
    border-radius: 18px; box-shadow: 0 12px 48px rgba(0,0,0,.4);
    padding: 6px 18px 20px;
  }
  .overlay-panel .topbar { position: sticky; top: 0; z-index: 2; background: inherit; padding-top: 12px; }
  .tabs { display: flex; flex-wrap: wrap; gap: 4px; margin: 10px 0 0; border-bottom: 1px solid var(--divider-color); }
  .tab {
    border: none; background: transparent; border-radius: 0; padding: 10px 16px;
    color: var(--secondary-text-color); font-weight: 600;
    border-bottom: 2px solid transparent; margin-bottom: -1px;
  }
  .tab:hover { background: transparent; color: var(--primary-text-color); }
  .tab.on { color: var(--primary-color); border-bottom-color: var(--primary-color); }
  .tab-body { padding-top: 14px; }
  .zone-add-row { display: flex; margin-bottom: 12px; }

  /* ---- History ---- */
  .overlay-panel.hist { width: min(560px, 96vw); padding: 6px 16px 18px; }
  .hist-head { position: sticky; top: 0; z-index: 2; background: inherit;
    display: flex; align-items: center; gap: 10px; padding: 12px 4px 12px;
    font-weight: 700; font-size: 1.2rem; color: var(--primary-text-color); }
  .hist-head > ha-icon { color: var(--primary-color); --mdc-icon-size: 24px; }
  .hist-list { display: flex; flex-direction: column; }
  .hist-day { font-size: .76rem; font-weight: 700; letter-spacing: .04em;
    text-transform: uppercase; color: var(--secondary-text-color); margin: 16px 4px 2px; }
  .hist-row { display: flex; align-items: flex-start; gap: 12px; padding: 11px 4px;
    border-top: 1px solid var(--divider-color); }
  .hist-day + .hist-row { border-top: none; }
  .hist-row > ha-icon { --mdc-icon-size: 22px; flex: none; margin-top: 1px; }
  .hist-main { flex: 1; min-width: 0; }
  .hist-title { font-weight: 600; color: var(--primary-text-color); }
  .hist-sub { color: var(--secondary-text-color); font-size: .85rem; margin-top: 1px; }
  .hist-time { color: var(--secondary-text-color); font-size: .82rem;
    font-variant-numeric: tabular-nums; flex: none; padding-top: 1px; }
  .h-blue > ha-icon { color: var(--primary-color); }
  .h-green > ha-icon { color: var(--success-color, #43a047); }
  .h-amber > ha-icon { color: var(--warning-color, #d68f00); }
  .h-red > ha-icon { color: var(--error-color); }
  .h-grey > ha-icon { color: var(--secondary-text-color); }

  /* ---- View mode (compact, read-only) ---- */
  ha-card.view .header { padding-bottom: 8px; }
  .vzone { display: flex; align-items: center; gap: 14px; padding: 16px 6px; }
  .vzone + .vzone { border-top: 1px solid var(--divider-color); }
  .vzone.running { background: rgba(3,169,244,.06); border-radius: 14px; margin: 4px 0; }
  .vzone.running + .vzone { border-top: none; }
  .vzone.disabled .info { opacity: .45; }
  .vactions { display: flex; align-items: center; gap: 12px; flex: none; }
  .runbtn { padding: 8px 12px; border: none; background: transparent; }
  .runbtn:hover { background: var(--secondary-background-color); }
  .runbtn ha-icon { --mdc-icon-size: 24px; }
  .setup-off .seqbar, .setup-off .raininfo { opacity: .5; }
  .vzone .info { flex: 1; min-width: 0; }
  .vname { font-weight: 650; font-size: 1.05rem; display: flex; align-items: center; gap: 9px; color: var(--primary-text-color); }
  .vmeta { color: var(--secondary-text-color); font-size: .84rem; margin-top: 3px; font-variant-numeric: tabular-nums; }
  .vmeta .dur { color: var(--primary-text-color); font-weight: 600; }
  .vprogress { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
  .vbar { flex: 1; height: 8px; border-radius: 999px; background: rgba(3,169,244,.16); overflow: hidden; }
  .vbar > i { display: block; height: 100%; width: 0%; background: var(--primary-color); border-radius: 999px; transition: width .5s linear; }
  .vleft { color: var(--primary-text-color); font-weight: 650; font-size: .85rem; font-variant-numeric: tabular-nums; min-width: 46px; text-align: right; }
  .pill { display: inline-flex; align-items: center; gap: 5px; font-size: .72rem; font-weight: 600; color: var(--primary-color); background: rgba(3,169,244,.13); border-radius: 999px; padding: 3px 9px; }
  .pill .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--primary-color); }
  .seqbar.view {
    display: flex; align-items: center; gap: 10px;
    margin: 0 0 14px; padding: 11px 14px; border-radius: 12px;
    font-size: .9rem; color: var(--secondary-text-color);
    background: rgba(67, 160, 71, .10);
  }
  .seqbar.view ha-icon { --mdc-icon-size: 20px; color: var(--success-color, #43a047); flex: none; }
  .seqbar.view b { color: var(--primary-text-color); font-variant-numeric: tabular-nums; font-weight: 650; }
  .seqedit { background: var(--secondary-background-color); border-radius: 12px; padding: 10px 14px; margin-top: 10px; }
  .seqedit .lbl { color: var(--secondary-text-color); margin-right: 4px; }
  .warn { color: var(--error-color); font-size: .85rem; margin-top: 8px; }
  /* [hidden] must win over the display rules above */
  .pill[hidden], .vprogress[hidden] { display: none; }
  .skipwarn {
    display: flex; align-items: center; gap: 9px; margin-top: 12px;
    padding: 10px 14px; border-radius: 12px; font-size: .9rem; font-weight: 500;
    color: var(--warning-color, #d68f00);
    background: rgba(214, 143, 0, .12);
  }
  .skipwarn ha-icon { --mdc-icon-size: 20px; }
  .raininfo {
    display: flex; align-items: center; gap: 10px;
    margin: 6px 0 10px; padding: 11px 14px; border-radius: 12px;
    font-size: .86rem; line-height: 1.35; color: var(--secondary-text-color);
    background: rgba(3, 169, 244, .07);
  }
  .raininfo ha-icon { --mdc-icon-size: 20px; color: var(--primary-color); flex: none; }
  .raininfo b { color: var(--primary-text-color); font-weight: 650; font-variant-numeric: tabular-nums; }
  .rainbox { background: var(--secondary-background-color); border-radius: 12px; padding: 10px 14px; margin-top: 12px; }
  .rainbox-title { font-weight: 600; font-size: .9rem; margin-bottom: 6px; }
  .rain-sec { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
  .rain-sec-label { font-weight: 600; font-size: .88rem; }
  .field-row.dim { opacity: .5; }
  input.num { font: inherit; padding: 7px 9px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color,#fff); color: var(--primary-text-color); width: 100%; box-sizing: border-box; }
  .gi-select { font: inherit; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color,#fff); color: var(--primary-text-color); width: 100%; box-sizing: border-box; }
  .seq-footer { display: flex; justify-content: center; gap: 12px; padding: 16px 6px 4px; margin-top: 6px; border-top: 1px solid var(--divider-color); }
  .title-input { font: inherit; font-size: 1.3rem; font-weight: 700; padding: 6px 10px; border-radius: 10px; border: 1px solid var(--divider-color); background: var(--card-background-color,#fff); color: var(--primary-text-color); min-width: 0; }
`;

class GardenIrrigationCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._setups = [];
    this._fetched = false;
    this._edit = false; // transient: true while building the edit overlay
    this._editOpen = false; // whether the edit overlay is shown
    this._tab = "zones"; // active overlay tab: zones | schedule | rain
    this._historyOpen = false;
    this._history = [];
    this._selected = null;
    this._addZoneOpen = false;
    this._addSetupOpen = false;
    this._sig = null;
    this._refs = {};
    this._skip = {};
    this._tick = this._tick.bind(this);
  }

  setConfig(config) {
    this._config = config || {};
    this._editOpen = !!(config && config.mode === "edit");
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._fetched) {
      this._fetched = true;
      this._fetch();
    }
    this._sync();
  }

  getCardSize() {
    const setup = this._currentSetup();
    return 3 + (setup ? setup.zones.length * 4 : 0);
  }

  static getStubConfig() {
    return { mode: "view" };
  }

  connectedCallback() {
    this._timer = setInterval(this._tick, 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    clearTimeout(this._retry);
  }

  /* ---------- data ---------- */

  _ws(message) {
    return this._hass.connection.sendMessagePromise(message);
  }

  async _fetch() {
    try {
      const res = await this._ws({ type: "garden_irrigation/get" });
      this._setups = res.setups || [];
      this._error = null;
    } catch (err) {
      this._setups = [];
      this._error = err && err.message ? err.message : String(err);
    }
    // Resolve the selected setup.
    if (!this._setups.find((s) => s.entry_id === this._selected)) {
      const pin = this._config.setup;
      const match = this._setups.find(
        (s) => s.entry_id === pin || s.name === pin
      );
      this._selected = (match || this._setups[0] || {}).entry_id || null;
    }
    this._sig = null;
    this._sync();
    this._fetchSkip();

    clearTimeout(this._retry);
    const cur = this._currentSetup();
    if (cur && cur.zones.some((z) => !z.entity_id)) {
      this._retry = setTimeout(() => this._fetch(), 1000);
    }
  }

  async _fetchSkip() {
    const setup = this._currentSetup();
    if (!setup) return;
    try {
      this._skip[setup.entry_id] = await this._ws({
        type: "garden_irrigation/skip_status",
        entry_id: setup.entry_id,
      });
    } catch (e) {
      this._skip[setup.entry_id] = { would_skip: false };
    }
    this._rebuild();
  }

  _currentSetup() {
    return this._setups.find((s) => s.entry_id === this._selected) || null;
  }

  /* ---------- render orchestration ---------- */

  _computeSig() {
    return JSON.stringify({
      editOpen: this._editOpen,
      tab: this._tab,
      historyOpen: this._historyOpen,
      history: this._historyOpen ? this._history : null,
      selected: this._selected,
      addZone: this._addZoneOpen,
      addSetup: this._addSetupOpen,
      error: this._error,
      setups: this._setups,
      skip: this._skip,
    });
  }

  _sync() {
    if (!this._hass) return;
    const sig = this._computeSig();
    if (sig !== this._sig) {
      this._sig = sig;
      this._render();
    }
    this._update();
  }

  _rebuild() {
    this._sig = null;
    this._sync();
  }

  _stateFor(zone) {
    if (!zone.entity_id) return null;
    return this._hass.states[zone.entity_id] || null;
  }

  /* ---------- build ---------- */

  _render() {
    this._refs = {};
    const root = document.createElement("div");
    const style = document.createElement("style");
    style.textContent = STYLES;
    root.appendChild(style);

    // Main card is always the compact view.
    this._edit = false;
    const card = document.createElement("ha-card");
    card.classList.add("view");
    this._fillCard(card);
    root.appendChild(card);

    // Edit happens in a large overlay so nothing gets squished.
    if (this._editOpen) {
      this._edit = true;
      root.appendChild(this._buildEditOverlay());
      this._edit = false;
    }

    if (this._historyOpen) root.appendChild(this._buildHistoryOverlay());

    this.shadowRoot.replaceChildren(root);
  }

  _fillCard(card) {
    card.appendChild(this._buildHeader());

    if (this._setups.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = this._edit
        ? this._t("noSetupsEdit")
        : this._t("noSetupsView");
      card.appendChild(empty);
      if (this._addSetupOpen && this._edit)
        card.appendChild(this._buildAddSetupForm());
      return;
    }

    if (this._addSetupOpen && this._edit)
      card.appendChild(this._buildAddSetupForm());

    const setup = this._currentSetup();
    if (!setup) return;

    if (setup.enabled === false) card.classList.add("setup-off");
    const rainInfo = this._buildRainInfo(setup, this._skip[setup.entry_id]);
    if (rainInfo) card.appendChild(rainInfo);
    if (this._edit) card.appendChild(this._buildSetupBar(setup));
    if (setup.mode === "sequential") card.appendChild(this._buildSeqBar(setup));
    if (this._edit && setup.mode === "sequential")
      card.appendChild(this._buildSeqScripts(setup));
    if (this._edit) card.appendChild(this._buildRainSkip(setup));
    if (this._addZoneOpen && this._edit)
      card.appendChild(this._buildAddZoneForm(setup));
    if (setup.zones.length === 0 && !this._addZoneOpen) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = this._t("noZones");
      card.appendChild(empty);
    }
    for (const zone of setup.zones) card.appendChild(this._buildZone(setup, zone));
    if (!this._edit && setup.zones.length)
      card.appendChild(this._buildViewFooter(setup));
  }

  _buildViewFooter(setup) {
    const footer = document.createElement("div");
    footer.className = "seq-footer";
    if (
      setup.mode === "sequential" &&
      setup.zones.length &&
      setup.enabled !== false
    )
      footer.appendChild(this._seqRunButton(setup));

    const hist = document.createElement("button");
    hist.innerHTML = `<ha-icon icon="mdi:history"></ha-icon> ${this._t("history")}`;
    hist.addEventListener("click", () => this._openHistory());
    footer.appendChild(hist);
    return footer;
  }

  async _openHistory() {
    this._historyOpen = true;
    this._rebuild();
    try {
      const res = await this._ws({
        type: "garden_irrigation/history",
        entry_id: this._currentSetup().entry_id,
      });
      this._history = res.events || [];
    } catch (e) {
      this._history = [];
    }
    this._rebuild();
  }

  _closeHistory() {
    this._historyOpen = false;
    this._rebuild();
  }

  _buildHistoryOverlay() {
    const overlay = document.createElement("div");
    overlay.className = "overlay";
    const bg = document.createElement("div");
    bg.className = "overlay-bg";
    bg.addEventListener("click", () => this._closeHistory());

    const panel = document.createElement("div");
    panel.className = "overlay-panel hist";

    const head = document.createElement("div");
    head.className = "hist-head";
    head.innerHTML = `<ha-icon icon="mdi:history"></ha-icon><span>${this._escape(
      this._t("history")
    )}</span>`;
    const spacer = document.createElement("div");
    spacer.style.flex = "1";
    const close = document.createElement("button");
    close.className = "icon-btn ghost";
    close.title = this._t("close");
    close.innerHTML = `<ha-icon icon="mdi:close"></ha-icon>`;
    close.addEventListener("click", () => this._closeHistory());
    head.append(spacer, close);
    panel.appendChild(head);

    const events = this._history || [];
    if (events.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = this._t("noHistory");
      panel.appendChild(empty);
    } else {
      const list = document.createElement("div");
      list.className = "hist-list";
      let lastDay = null;
      for (const ev of events) {
        const d = new Date(ev.ts);
        const dayKey = d.toDateString();
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dh = document.createElement("div");
          dh.className = "hist-day";
          dh.textContent = this._formatDay(d);
          list.appendChild(dh);
        }
        list.appendChild(this._buildHistRow(ev, d));
      }
      panel.appendChild(list);
    }

    overlay.append(bg, panel);
    return overlay;
  }

  _buildHistRow(ev, d) {
    const row = document.createElement("div");
    const style = this._histStyle(ev.type);
    row.className = "hist-row " + style.cls;
    const t = this._histText(ev);
    row.innerHTML =
      `<ha-icon icon="${style.icon}"></ha-icon>` +
      `<div class="hist-main"><div class="hist-title">${this._escape(t.title)}</div>` +
      (t.sub ? `<div class="hist-sub">${this._escape(t.sub)}</div>` : "") +
      `</div>` +
      `<div class="hist-time">${this._escape(this._formatClock(d))}</div>`;
    return row;
  }

  _histStyle(type) {
    return (
      {
        sequence: { icon: "mdi:playlist-play", cls: "h-blue" },
        start: { icon: "mdi:play-circle", cls: "h-blue" },
        finish: { icon: "mdi:check-circle", cls: "h-green" },
        stop: { icon: "mdi:stop-circle", cls: "h-grey" },
        skip: { icon: "mdi:weather-rainy", cls: "h-amber" },
        error: { icon: "mdi:alert-circle", cls: "h-red" },
      }[type] || { icon: "mdi:information-outline", cls: "h-grey" }
    );
  }

  _histText(ev) {
    switch (ev.type) {
      case "sequence":
        return { title: this._t("histSequence"), sub: "" };
      case "start":
        return {
          title: ev.zone,
          sub: `${this._t("histStarted")} · ${ev.minutes} min · ${this._t(
            ev.source === "scheduled" ? "scheduled" : "manual"
          )}`,
        };
      case "finish":
        return { title: ev.zone, sub: this._t("histFinished") };
      case "stop":
        return { title: ev.zone, sub: this._t("histStopped") };
      case "skip":
        return {
          title: this._t("histSkipped"),
          sub:
            ev.detail === "rain_forecast"
              ? this._t("histSkipForecast")
              : this._t("histSkipRecent"),
        };
      case "error":
        return { title: ev.zone, sub: this._t("histOffFailed") };
      default:
        return { title: ev.type, sub: "" };
    }
  }

  _formatDay(d) {
    const now = new Date();
    const y = new Date(now);
    y.setDate(now.getDate() - 1);
    if (d.toDateString() === now.toDateString()) return this._t("today");
    if (d.toDateString() === y.toDateString()) return this._t("yesterday");
    return d.toLocaleDateString(this._lang() === "pt" ? "pt-PT" : "en", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  }

  _formatClock(d) {
    return d.toLocaleTimeString(this._lang() === "pt" ? "pt-PT" : "en", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  _buildEditOverlay() {
    const overlay = document.createElement("div");
    overlay.className = "overlay";
    const bg = document.createElement("div");
    bg.className = "overlay-bg";
    bg.addEventListener("click", () => this._closeEdit());
    const panel = document.createElement("div");
    panel.className = "overlay-panel";
    this._fillEditPanel(panel);
    overlay.append(bg, panel);
    return overlay;
  }

  _fillEditPanel(panel) {
    const setup = this._currentSetup();

    const top = document.createElement("div");
    top.className = "topbar";
    top.appendChild(this._buildHeader());
    if (this._setups.length && setup) top.appendChild(this._buildTabBar());
    panel.appendChild(top);

    if (this._setups.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = this._t("noSetupsEdit");
      panel.appendChild(empty);
      if (this._addSetupOpen) panel.appendChild(this._buildAddSetupForm());
      return;
    }

    if (this._addSetupOpen) panel.appendChild(this._buildAddSetupForm());
    if (!setup) return;

    const body = document.createElement("div");
    body.className = "tab-body";

    if (this._tab === "notify") {
      body.appendChild(this._buildNotify(setup));
    } else if (this._tab === "rain") {
      body.appendChild(this._buildRainSkip(setup));
    } else if (this._tab === "scripts") {
      if (setup.mode === "sequential") {
        body.appendChild(this._buildSeqScripts(setup));
      } else {
        const hint = document.createElement("div");
        hint.className = "empty";
        hint.textContent = this._t("scriptsHint");
        body.appendChild(hint);
      }
    } else if (this._tab === "schedule") {
      body.appendChild(this._buildSetupBar(setup));
      if (setup.mode === "sequential") {
        body.appendChild(this._buildSeqBar(setup));
      } else {
        const hint = document.createElement("div");
        hint.className = "empty";
        hint.textContent = this._t("specificHint");
        body.appendChild(hint);
      }
    } else {
      // zones
      const addRow = document.createElement("div");
      addRow.className = "zone-add-row";
      const addBtn = document.createElement("button");
      addBtn.className = "add-zone";
      addBtn.innerHTML = `<ha-icon icon="mdi:plus"></ha-icon> ${this._t("addZone")}`;
      addBtn.addEventListener("click", () => {
        this._addZoneOpen = !this._addZoneOpen;
        this._rebuild();
      });
      addRow.appendChild(addBtn);
      body.appendChild(addRow);

      if (this._addZoneOpen) body.appendChild(this._buildAddZoneForm(setup));
      if (setup.zones.length === 0 && !this._addZoneOpen) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = this._t("noZones");
        body.appendChild(empty);
      }
      for (const zone of setup.zones)
        body.appendChild(this._buildZone(setup, zone));
    }

    panel.appendChild(body);
  }

  _buildTabBar() {
    const bar = document.createElement("div");
    bar.className = "tabs";
    [
      ["zones", this._t("tabZones")],
      ["schedule", this._t("tabSchedule")],
      ["scripts", this._t("tabScripts")],
      ["rain", this._t("tabRain")],
      ["notify", this._t("tabNotify")],
    ].forEach(([id, label]) => {
      const b = document.createElement("button");
      b.className = "tab" + (this._tab === id ? " on" : "");
      b.textContent = label;
      b.addEventListener("click", () => {
        this._tab = id;
        this._rebuild();
      });
      bar.appendChild(b);
    });
    return bar;
  }

  _closeEdit() {
    this._editOpen = false;
    this._addZoneOpen = false;
    this._addSetupOpen = false;
    this._rebuild();
  }

  _showEditButton() {
    // edit_button: "always" (default) | "admin" | "never"
    const pref = this._config.edit_button || "always";
    if (pref === "never") return false;
    if (pref === "admin")
      return !!(this._hass && this._hass.user && this._hass.user.is_admin);
    return true;
  }

  _buildHeader() {
    const header = document.createElement("div");
    header.className = "header";

    const icon = document.createElement("ha-icon");
    icon.setAttribute("icon", "mdi:sprinkler-variant");
    header.appendChild(icon);

    const setup = this._currentSetup();

    // Setup switcher (when more than one setup exists).
    if (this._setups.length > 1 && setup) {
      const sel = document.createElement("select");
      sel.className = "setup-select";
      for (const s of this._setups) {
        const o = document.createElement("option");
        o.value = s.entry_id;
        o.textContent = s.name;
        if (s.entry_id === this._selected) o.selected = true;
        sel.appendChild(o);
      }
      sel.addEventListener("change", () => {
        this._selected = sel.value;
        this._rebuild();
        this._fetchSkip();
      });
      header.appendChild(sel);
    }

    // Title: editable in edit mode, static otherwise.
    if (this._edit && setup) {
      const input = document.createElement("input");
      input.className = "title-input";
      input.type = "text";
      input.value = setup.name || "";
      input.title = this._t("renameSetup");
      input.addEventListener("change", () => {
        const v = input.value.trim();
        if (v && v !== setup.name)
          this._updateSetup(setup.entry_id, { name: v });
      });
      header.appendChild(input);
    } else if (this._setups.length <= 1 || !setup) {
      const h1 = document.createElement("h1");
      // The setup name is authoritative; card `title` is only a fallback when
      // no setup is loaded yet.
      h1.textContent = setup ? setup.name : this._config.title || this._t("title");
      header.appendChild(h1);
    }

    const spacer = document.createElement("div");
    spacer.className = "spacer";
    header.appendChild(spacer);

    // Right-side controls grouped tightly together.
    const actions = document.createElement("div");
    actions.className = "head-actions";

    if (this._edit) {
      const addSetup = document.createElement("button");
      addSetup.innerHTML = `<ha-icon icon="mdi:folder-plus-outline"></ha-icon> ${this._t("addSetup")}`;
      addSetup.addEventListener("click", () => {
        this._addSetupOpen = !this._addSetupOpen;
        this._rebuild();
      });
      actions.appendChild(addSetup);
    }

    const isEditCtx = this._edit;
    if (isEditCtx || this._showEditButton()) {
      const modeBtn = document.createElement("button");
      modeBtn.className = "icon-btn ghost" + (isEditCtx ? " active" : "");
      modeBtn.title = isEditCtx ? this._t("done") : this._t("edit");
      modeBtn.innerHTML = isEditCtx
        ? `<ha-icon icon="mdi:check"></ha-icon>`
        : `<ha-icon icon="mdi:pencil"></ha-icon>`;
      modeBtn.addEventListener("click", () => {
        if (isEditCtx) {
          this._closeEdit();
        } else {
          this._editOpen = true;
          this._addZoneOpen = false;
          this._addSetupOpen = false;
          this._rebuild();
        }
      });
      actions.appendChild(modeBtn);
    }

    // View mode: enable/disable toggle sits AFTER the edit icon.
    if (!this._edit && setup) {
      const enabled = setup.enabled !== false;
      const sw = this._switch(enabled, (v) =>
        this._updateSetup(setup.entry_id, { enabled: v })
      );
      sw.title = enabled ? this._t("disable") : this._t("enable");
      actions.appendChild(sw);
    }

    header.appendChild(actions);
    return header;
  }

  _buildSetupBar(setup) {
    const bar = document.createElement("div");
    bar.className = "setup-bar";

    const lbl = document.createElement("span");
    lbl.className = "lbl";
    lbl.textContent = this._t("scheduling");
    bar.appendChild(lbl);

    const toggle = document.createElement("div");
    toggle.className = "toggle";
    [
      ["sequential", this._t("sequential")],
      ["specific", this._t("specific")],
    ].forEach(([value, label]) => {
      const b = document.createElement("button");
      b.textContent = label;
      if (setup.mode === value) b.classList.add("on");
      b.addEventListener("click", () => {
        if (setup.mode !== value) this._updateSetup(setup.entry_id, { mode: value });
      });
      toggle.appendChild(b);
    });
    bar.appendChild(toggle);

    const spacer = document.createElement("div");
    spacer.style.flex = "1";
    bar.appendChild(spacer);

    const del = document.createElement("button");
    del.className = "icon-btn";
    del.title = this._t("deleteSetup");
    del.innerHTML = `<ha-icon icon="mdi:trash-can-outline"></ha-icon>`;
    del.addEventListener("click", () => this._deleteSetup(setup));
    bar.appendChild(del);

    return bar;
  }

  _buildRainInfo(setup, skip) {
    // Actively skipping right now → amber warning (both modes).
    if (skip && skip.would_skip) return this._buildSkipBanner(skip);
    // Edit mode has the full rain-skip config box instead.
    if (this._edit) return null;
    const recentActive = setup.rain_entity && setup.rain_enabled !== false;
    const forecastActive = setup.forecast_entity && setup.forecast_enabled !== false;
    if (!recentActive && !forecastActive) return null;

    const parts = [];
    if (recentActive) {
      const dom = setup.rain_entity.split(".")[0];
      parts.push(
        dom === "binary_sensor"
          ? this._t("rainInfoRecentBinary", setup.rain_hours)
          : this._t("rainInfoRecent", setup.rain_threshold, setup.rain_hours)
      );
    }
    if (forecastActive) {
      parts.push(
        this._t("rainInfoForecast", setup.forecast_threshold, setup.forecast_hours)
      );
    }

    const div = document.createElement("div");
    div.className = "raininfo";
    div.innerHTML =
      `<ha-icon icon="mdi:weather-partly-rainy"></ha-icon>` +
      `<span>${this._t("rainInfoPrefix")}${parts.join(this._t("rainInfoOr"))}</span>`;
    return div;
  }

  _buildSkipBanner(skip) {
    const div = document.createElement("div");
    div.className = "skipwarn";
    const text =
      skip.reason === "rain_forecast"
        ? this._t("skipForecast")
        : this._t("skipRain");
    div.innerHTML = `<ha-icon icon="mdi:weather-rainy"></ha-icon><span>${this._escape(
      text
    )}</span>`;
    return div;
  }

  _buildRainSkip(setup) {
    const box = document.createElement("div");
    box.className = "rainbox";
    const h = document.createElement("div");
    h.className = "rainbox-title";
    h.textContent = this._t("rainSkipTitle");
    box.appendChild(h);

    const r1 = document.createElement("div");
    r1.className = "field-row";
    r1.appendChild(
      this._labeledField(
        this._t("rainEntity"),
        this._entityPicker(
          setup.rain_entity,
          ["sensor", "weather", "binary_sensor"],
          (v) => this._updateSetup(setup.entry_id, { rain_entity: v || null })
        ).el
      )
    );
    r1.appendChild(
      this._numField(this._t("lookback"), setup.rain_hours, 1, 72, 1, (v) =>
        this._updateSetup(setup.entry_id, { rain_hours: v })
      )
    );
    r1.appendChild(
      this._numField(this._t("rainThreshold"), setup.rain_threshold, 0, 50, 0.1, (v) =>
        this._updateSetup(setup.entry_id, { rain_threshold: v })
      )
    );
    box.appendChild(
      this._rainSection(
        this._t("skipIfRained"),
        setup.rain_enabled !== false,
        (v) => this._updateSetup(setup.entry_id, { rain_enabled: v }),
        r1
      )
    );

    const r2 = document.createElement("div");
    r2.className = "field-row";
    r2.appendChild(
      this._labeledField(
        this._t("forecastEntity"),
        this._entityPicker(setup.forecast_entity, ["weather"], (v) =>
          this._updateSetup(setup.entry_id, { forecast_entity: v || null })
        ).el
      )
    );
    r2.appendChild(
      this._numField(this._t("lookahead"), setup.forecast_hours, 1, 72, 1, (v) =>
        this._updateSetup(setup.entry_id, { forecast_hours: v })
      )
    );
    r2.appendChild(
      this._numField(this._t("rainChance"), setup.forecast_threshold, 0, 100, 5, (v) =>
        this._updateSetup(setup.entry_id, { forecast_threshold: v })
      )
    );
    box.appendChild(
      this._rainSection(
        this._t("skipIfForecast"),
        setup.forecast_enabled !== false,
        (v) => this._updateSetup(setup.entry_id, { forecast_enabled: v }),
        r2
      )
    );
    return box;
  }

  _buildNotify(setup) {
    const box = document.createElement("div");
    box.className = "rainbox";
    const enabled = setup.notify_enabled === true;

    const head = document.createElement("div");
    head.className = "rain-sec";
    const sw = this._switch(enabled, (v) =>
      this._updateSetup(setup.entry_id, { notify_enabled: v })
    );
    sw.title = enabled ? this._t("disable") : this._t("enable");
    const l = document.createElement("span");
    l.className = "rain-sec-label";
    l.textContent = this._t("notifyTitle");
    head.append(sw, l);
    box.appendChild(head);

    const row = document.createElement("div");
    row.className = "field-row" + (enabled ? "" : " dim");
    row.appendChild(
      this._labeledField(this._t("notifyTarget"), this._notifySelect(setup))
    );
    box.appendChild(row);

    const hint = document.createElement("div");
    hint.className = "hist-sub";
    hint.style.marginTop = "8px";
    hint.textContent = this._t("notifyHint");
    box.appendChild(hint);

    const testRow = document.createElement("div");
    testRow.style.marginTop = "10px";
    const testBtn = document.createElement("button");
    testBtn.innerHTML = `<ha-icon icon="mdi:bell-ring-outline"></ha-icon> ${this._t(
      "notifyTest"
    )}`;
    testBtn.disabled = !setup.notify_target;
    testBtn.addEventListener("click", async () => {
      try {
        await this._ws({
          type: "garden_irrigation/notify_test",
          entry_id: setup.entry_id,
        });
        this._toast(this._t("notifyTestSent"));
      } catch (e) {
        this._toast(this._t("notifyTestFail"));
      }
    });
    testRow.appendChild(testBtn);
    box.appendChild(testRow);
    return box;
  }

  _notifyTargets() {
    const opts = [];
    // Notify entities (modern; used via notify.send_message).
    for (const eid of Object.keys((this._hass && this._hass.states) || {})) {
      if (eid.startsWith("notify.")) {
        const st = this._hass.states[eid];
        opts.push({ value: eid, label: (st.attributes && st.attributes.friendly_name) || eid });
      }
    }
    // Legacy notify services (e.g. mobile_app_*), used via notify.<service>.
    const svc = (this._hass && this._hass.services && this._hass.services.notify) || {};
    for (const name of Object.keys(svc)) {
      if (name === "send_message") continue;
      const value = `notify.${name}`;
      if (!opts.some((o) => o.value === value)) opts.push({ value, label: value });
    }
    return opts.sort((a, b) => a.label.localeCompare(b.label));
  }

  _notifySelect(setup) {
    const sel = document.createElement("select");
    sel.className = "gi-select";
    const cur = setup.notify_target || "";

    const none = document.createElement("option");
    none.value = "";
    none.textContent = "—";
    sel.appendChild(none);

    let found = false;
    for (const t of this._notifyTargets()) {
      const o = document.createElement("option");
      o.value = t.value;
      o.textContent = t.label;
      if (t.value === cur) {
        o.selected = true;
        found = true;
      }
      sel.appendChild(o);
    }
    if (cur && !found) {
      const o = document.createElement("option");
      o.value = cur;
      o.textContent = cur;
      o.selected = true;
      sel.appendChild(o);
    }

    sel.addEventListener("change", () =>
      this._updateSetup(setup.entry_id, { notify_target: sel.value || null })
    );
    return sel;
  }

  _rainSection(label, enabled, onToggle, fieldRow) {
    const wrap = document.createElement("div");
    const head = document.createElement("div");
    head.className = "rain-sec";
    const sw = this._switch(enabled, onToggle);
    sw.title = enabled ? this._t("disable") : this._t("enable");
    const l = document.createElement("span");
    l.className = "rain-sec-label";
    l.textContent = label;
    head.append(sw, l);
    wrap.appendChild(head);
    if (!enabled) fieldRow.classList.add("dim");
    wrap.appendChild(fieldRow);
    return wrap;
  }

  _labeledField(label, el) {
    const f = document.createElement("div");
    f.className = "field";
    const l = document.createElement("label");
    l.textContent = label;
    f.append(l, el);
    return f;
  }

  _numField(label, value, min, max, step, onChange) {
    const f = document.createElement("div");
    f.className = "field";
    const l = document.createElement("label");
    l.textContent = label;
    const i = document.createElement("input");
    i.type = "number";
    i.className = "num";
    i.min = min;
    i.max = max;
    i.step = step;
    i.value = value != null ? value : "";
    i.addEventListener("change", () => {
      const v = parseFloat(i.value);
      if (!isNaN(v)) onChange(v);
    });
    f.append(l, i);
    return f;
  }

  _buildSeqBar(setup) {
    return this._edit ? this._buildSeqBarEdit(setup) : this._buildSeqBarView(setup);
  }

  _buildSeqScripts(setup) {
    const wrap = document.createElement("div");
    wrap.className = "field-row";
    wrap.appendChild(
      this._scriptField(this._t("preScript"), setup.pre_script, (v) =>
        this._updateSetup(setup.entry_id, { pre_script: v || null })
      )
    );
    wrap.appendChild(
      this._scriptField(this._t("postScript"), setup.post_script, (v) =>
        this._updateSetup(setup.entry_id, { post_script: v || null })
      )
    );
    return wrap;
  }

  _seqRunButton(setup) {
    const anyRunning = setup.zones.some((z) => {
      const st = this._stateFor(z);
      return st && st.state === "on";
    });
    const run = document.createElement("button");
    if (anyRunning) {
      run.className = "stop";
      run.innerHTML = `<ha-icon icon="mdi:stop"></ha-icon> ${this._t("stop")}`;
      run.addEventListener("click", () =>
        this._ws({ type: "garden_irrigation/setup/stop", entry_id: setup.entry_id })
      );
    } else {
      run.innerHTML = `<ha-icon icon="mdi:play"></ha-icon> ${this._t("runSequence")}`;
      run.addEventListener("click", () =>
        this._ws({ type: "garden_irrigation/setup/run", entry_id: setup.entry_id })
      );
    }
    return run;
  }

  _buildSeqBarView(setup) {
    const bar = document.createElement("div");
    bar.className = "seqbar view";

    const times = (setup.start_times || []).map((s) => s.time);
    const timesHtml = times.length
      ? times.map((t) => `<b>${this._escape(t)}</b>`).join(", ")
      : "<b>—</b>";
    const dayText = this._uniformDaysText(setup.start_times);

    bar.innerHTML =
      `<ha-icon icon="mdi:clock-outline"></ha-icon>` +
      `<span>${this._escape(this._t("starts"))} ${timesHtml}${
        dayText ? " · " + this._escape(dayText) : ""
      }</span>`;
    return bar;
  }

  _buildSeqBarEdit(setup) {
    const box = document.createElement("div");
    box.className = "seqedit";

    const chips = document.createElement("div");
    chips.className = "chips";

    const lbl = document.createElement("span");
    lbl.className = "lbl";
    lbl.textContent = this._t("startsLabel");
    chips.appendChild(lbl);

    const starts = setup.start_times || [];
    if (starts.length === 0) {
      const none = document.createElement("span");
      none.className = "no-sched";
      none.textContent = this._t("noStartTimes");
      chips.appendChild(none);
    }
    starts.forEach((s, index) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = `<ha-icon icon="mdi:clock-outline"></ha-icon><span>${this._escape(
        s.time
      )}</span><span class="x" title="Remove">✕</span>`;
      chip
        .querySelector(".x")
        .addEventListener("click", () => this._removeStartTime(setup, index));
      chips.appendChild(chip);
    });

    const time = this._make24hTime("06:00", null);
    chips.appendChild(time.wrap);
    const add = document.createElement("button");
    add.textContent = this._t("add");
    add.addEventListener("click", () => this._addStartTime(setup, time.get()));
    chips.appendChild(add);

    box.appendChild(chips);

    const collisions = this._startCollisions(setup);
    if (collisions.length) {
      const warn = document.createElement("div");
      warn.className = "warn";
      warn.textContent = this._t(
        "collisionWarn",
        setup.total_duration,
        collisions.join("; ")
      );
      box.appendChild(warn);
    }

    return box;
  }

  _uniformDaysText(starts) {
    if (!starts || !starts.length) return "";
    const norm = (s) =>
      (s.days && s.days.length ? [...s.days] : [...WEEKDAYS]).sort().join(",");
    const first = norm(starts[0]);
    if (starts.every((s) => norm(s) === first))
      return this._formatDays(starts[0].days);
    return "";
  }

  _startCollisions(setup, extra) {
    const total = setup.total_duration || 0;
    if (total <= 0) return [];
    const list = (setup.start_times || []).slice();
    if (extra) list.push(extra);
    const windows = [];
    for (const s of list) {
      const [h, m] = s.time.split(":").map(Number);
      const start = h * 60 + m;
      const days = s.days && s.days.length ? s.days : WEEKDAYS;
      for (const d of days) windows.push([d, start, s.time]);
    }
    const seen = new Set();
    const out = [];
    for (let i = 0; i < windows.length; i++) {
      for (let j = i + 1; j < windows.length; j++) {
        const [da, sa, ta] = windows[i];
        const [db, sb, tb] = windows[j];
        if (da !== db) continue;
        if (Math.abs(sa - sb) < total) {
          const key = [ta, tb].sort().join("|") + da;
          if (seen.has(key)) continue;
          seen.add(key);
          const lang = this._lang();
          const sep = lang === "pt" ? " e " : " and ";
          const on = lang === "pt" ? " — " : " on ";
          out.push(`${ta}${sep}${tb}${on}${DAY_LABEL[lang][da] || da}`);
        }
      }
    }
    return out;
  }

  async _addStartTime(setup, time) {
    const introduced = this._startCollisions(setup, {
      time,
      days: WEEKDAYS,
    }).filter((c) => !this._startCollisions(setup).includes(c));
    if (introduced.length) {
      this._toast(
        this._t("collides", setup.total_duration, introduced.join("; "))
      );
      return;
    }
    try {
      await this._ws({
        type: "garden_irrigation/setup/start_time/add",
        entry_id: setup.entry_id,
        time,
        days: WEEKDAYS,
      });
      await this._fetch();
    } catch (err) {
      this._toast(this._t("addStartFail", err.message || err));
    }
  }

  async _removeStartTime(setup, index) {
    try {
      await this._ws({
        type: "garden_irrigation/setup/start_time/remove",
        entry_id: setup.entry_id,
        index,
      });
      await this._fetch();
    } catch (err) {
      this._toast(this._t("removeStartFail", err.message || err));
    }
  }

  _buildZone(setup, zone) {
    return this._edit
      ? this._buildZoneEdit(setup, zone)
      : this._buildZoneView(setup, zone);
  }

  _zoneMetaHtml(setup, zone) {
    const dur = `<span class="dur">${zone.duration} min</span>`;
    if (setup.mode === "sequential") {
      const idx = setup.zones.findIndex((z) => z.zone_id === zone.zone_id);
      return `${dur} · ${this._escape(this._t("runsNth", idx + 1))}`;
    }
    const times = (zone.schedules || []).map((s) => this._escape(s.time));
    if (times.length === 0)
      return `${dur} · <span style="opacity:.85">${this._escape(
        this._t("noSchedules").toLowerCase()
      )}</span>`;
    const shown = times.slice(0, 3).join(" · ");
    const extra = times.length > 3 ? ` +${times.length - 3}` : "";
    return `${dur} · ${shown}${extra}`;
  }

  _buildZoneView(setup, zone) {
    const refs = { kind: "view" };
    const el = document.createElement("div");
    el.className = "vzone";
    refs.el = el;

    const info = document.createElement("div");
    info.className = "info";

    const name = document.createElement("div");
    name.className = "vname";
    const nameText = document.createElement("span");
    nameText.textContent = zone.name;
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.hidden = true;
    pill.innerHTML = `<span class="dot"></span><span class="pill-text"></span>`;
    name.append(nameText, pill);
    info.appendChild(name);
    refs.pill = pill;
    refs.pillText = pill.querySelector(".pill-text");

    const meta = document.createElement("div");
    meta.className = "vmeta";
    meta.innerHTML = this._zoneMetaHtml(setup, zone);
    info.appendChild(meta);

    const progress = document.createElement("div");
    progress.className = "vprogress";
    progress.hidden = true;
    const bar = document.createElement("div");
    bar.className = "vbar";
    const fill = document.createElement("i");
    bar.appendChild(fill);
    const left = document.createElement("span");
    left.className = "vleft";
    progress.append(bar, left);
    info.appendChild(progress);
    refs.progress = progress;
    refs.fill = fill;
    refs.left = left;
    refs.total = Math.max(1, zone.duration * 60);

    el.appendChild(info);

    const setupEnabled = setup.enabled !== false;
    const zoneEnabled = zone.enabled !== false;
    if (!setupEnabled || !zoneEnabled) el.classList.add("disabled");

    const actions = document.createElement("div");
    actions.className = "vactions";
    // Run button (always available — a manual run works even on a disabled zone),
    // then the per-zone enable toggle. Both hidden only when the whole setup is off.
    if (setupEnabled) {
      const action = document.createElement("button");
      action.addEventListener("click", () => this._toggleRun(zone));
      actions.appendChild(action);
      refs.action = action;

      const sw = this._switch(zoneEnabled, (v) =>
        this._updateZone(setup.entry_id, zone.zone_id, { enabled: v })
      );
      sw.title = zoneEnabled ? this._t("disable") : this._t("enable");
      actions.appendChild(sw);
    }
    el.appendChild(actions);

    this._refs[zone.zone_id] = refs;
    return el;
  }

  _buildZoneEdit(setup, zone) {
    const refs = { kind: "edit" };
    const el = document.createElement("div");
    el.className = "zone";
    refs.el = el;

    // Head
    const head = document.createElement("div");
    head.className = "zone-head";
    const titles = document.createElement("div");
    titles.className = "titles";

    const nameRow = document.createElement("div");
    nameRow.className = "zone-name";
    if (this._edit) {
      const nameInput = document.createElement("input");
      nameInput.type = "text";
      nameInput.value = zone.name || "";
      nameInput.addEventListener("change", () => {
        const v = nameInput.value.trim();
        if (v && v !== zone.name)
          this._updateZone(setup.entry_id, zone.zone_id, { name: v });
      });
      nameRow.appendChild(nameInput);
    } else {
      const n = document.createElement("span");
      n.textContent = zone.name;
      nameRow.appendChild(n);
    }
    titles.appendChild(nameRow);

    // Switch line — shown in edit mode (editable picker), hidden in view.
    if (this._edit) {
      const subWrap = document.createElement("div");
      subWrap.className = "field-row";
      const swField = document.createElement("div");
      swField.className = "field";
      const swLabel = document.createElement("label");
      swLabel.textContent = this._t("switchRelay");
      const sw = this._entityPicker(
        zone.switch_entity,
        ["switch", "input_boolean"],
        (v) => v && this._updateZone(setup.entry_id, zone.zone_id, { switch_entity: v })
      );
      swField.append(swLabel, sw.el);

      const preField = this._scriptField(this._t("preScriptShort"), zone.pre_script, (v) =>
        this._updateZone(setup.entry_id, zone.zone_id, { pre_script: v || null })
      );
      const postField = this._scriptField(this._t("postScriptShort"), zone.post_script, (v) =>
        this._updateZone(setup.entry_id, zone.zone_id, { post_script: v || null })
      );
      subWrap.append(swField, preField, postField);
      titles.appendChild(subWrap);
    }

    head.appendChild(titles);

    if (this._edit) {
      const del = document.createElement("button");
      del.className = "icon-btn";
      del.title = this._t("deleteZone");
      del.innerHTML = `<ha-icon icon="mdi:trash-can-outline"></ha-icon>`;
      del.addEventListener("click", () => this._deleteZone(setup, zone));
      head.appendChild(del);
    }
    el.appendChild(head);

    // Duration slider (always editable)
    const durRow = document.createElement("div");
    durRow.className = "row";
    durRow.innerHTML = `<span class="label">${this._t("duration")}</span>`;
    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "1";
    slider.max = "60";
    slider.step = "1";
    slider.value = String(zone.duration);
    const durVal = document.createElement("span");
    durVal.className = "dur-value";
    durVal.textContent = `${zone.duration} min`;
    slider.addEventListener("input", () => {
      durVal.textContent = `${slider.value} min`;
    });
    slider.addEventListener("change", () =>
      this._updateZone(setup.entry_id, zone.zone_id, {
        duration: parseInt(slider.value, 10),
      })
    );
    durRow.append(slider, durVal);
    el.appendChild(durRow);
    refs.slider = slider;
    refs.durVal = durVal;

    // Schedules (specific mode only)
    if (setup.mode === "specific") {
      const schedLabel = document.createElement("div");
      schedLabel.className = "sched-label";
      schedLabel.textContent = this._t("schedulesLabel");
      el.appendChild(schedLabel);

      const chips = document.createElement("div");
      chips.className = "chips";
      const schedules = zone.schedules || [];
      if (schedules.length === 0) {
        const none = document.createElement("span");
        none.className = "no-sched";
        none.textContent = this._t("noSchedules");
        chips.appendChild(none);
      }
      schedules.forEach((s, index) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.innerHTML = `<ha-icon icon="mdi:clock-outline"></ha-icon><span>${this._escape(
          s.time
        )}</span><span class="x" title="Remove">✕</span>`;
        chip
          .querySelector(".x")
          .addEventListener("click", () =>
            this._removeSchedule(setup.entry_id, zone.zone_id, index)
          );
        chips.appendChild(chip);
      });

      const time = this._make24hTime("06:00", null);
      chips.appendChild(time.wrap);
      const addBtn = document.createElement("button");
      addBtn.textContent = this._t("add");
      addBtn.addEventListener("click", () =>
        this._addSchedule(setup.entry_id, zone.zone_id, time.get())
      );
      chips.appendChild(addBtn);
      el.appendChild(chips);
    }

    // Edit mode is for configuration only — no Run/Stop row here.
    this._refs[zone.zone_id] = refs;
    return el;
  }

  _scriptField(label, value, onChange) {
    const field = document.createElement("div");
    field.className = "field";
    const l = document.createElement("label");
    l.textContent = label;
    const picker = this._entityPicker(value, ["script"], onChange);
    field.append(l, picker.el);
    return field;
  }

  _buildAddZoneForm(setup) {
    const form = document.createElement("div");
    form.className = "form";
    form.innerHTML = `
      <div class="field"><label>${this._t("zoneName")}</label><input type="text" id="z-name" placeholder="${this._t("zoneNamePh")}" /></div>
      <div class="field"><label>${this._t("switchRelay")}</label><div id="z-picker"></div></div>
      <div class="field"><label>${this._t("durationMinutes")}</label><input type="number" id="z-dur" min="1" max="60" value="10" /></div>
      <div class="form-actions"><button id="z-cancel">${this._t("cancel")}</button><button id="z-save" class="primary">${this._t("saveZone")}</button></div>
    `;
    const sw = this._entityPicker(null, ["switch", "input_boolean"], () => {});
    form.querySelector("#z-picker").appendChild(sw.el);
    form.querySelector("#z-cancel").addEventListener("click", () => {
      this._addZoneOpen = false;
      this._rebuild();
    });
    form.querySelector("#z-save").addEventListener("click", async () => {
      const name = form.querySelector("#z-name").value.trim();
      const switch_entity = sw.get();
      const duration = parseInt(form.querySelector("#z-dur").value, 10) || 10;
      if (!name || !switch_entity) {
        this._toast(this._t("needNameSwitch"));
        return;
      }
      try {
        await this._ws({
          type: "garden_irrigation/zone/add",
          entry_id: setup.entry_id,
          name,
          switch_entity,
          duration,
        });
        this._addZoneOpen = false;
        await this._fetch();
      } catch (err) {
        this._toast(this._t("addZoneFail", err.message || err));
      }
    });
    return form;
  }

  _buildAddSetupForm() {
    const form = document.createElement("div");
    form.className = "form";
    form.innerHTML = `
      <div class="field"><label>${this._t("setupName")}</label><input type="text" id="s-name" placeholder="${this._t("setupNamePh")}" /></div>
      <div class="field"><label>${this._t("schedulingMode")}</label>
        <div class="toggle" id="s-mode">
          <button data-v="specific" class="on">${this._t("specific")}</button>
          <button data-v="sequential">${this._t("sequential")}</button>
        </div>
      </div>
      <div class="field" id="s-seq" hidden>
        <label>${this._t("startDays")}</label>
        <div class="seq-bar" id="s-seqbar"></div>
      </div>
      <div class="form-actions"><button id="s-cancel">${this._t("cancel")}</button><button id="s-save" class="primary">${this._t("createSetup")}</button></div>
    `;
    let mode = "specific";
    const seqWrap = form.querySelector("#s-seq");
    const seqBar = form.querySelector("#s-seqbar");
    const time = this._make24hTime("06:00", null);
    const days = this._makeDaysEditor(WEEKDAYS, true, null);
    seqBar.append(time.wrap, days.wrap);

    form.querySelectorAll("#s-mode button").forEach((b) => {
      b.addEventListener("click", () => {
        mode = b.dataset.v;
        form.querySelectorAll("#s-mode button").forEach((x) => x.classList.remove("on"));
        b.classList.add("on");
        seqWrap.hidden = mode !== "sequential";
      });
    });

    form.querySelector("#s-cancel").addEventListener("click", () => {
      this._addSetupOpen = false;
      this._rebuild();
    });
    form.querySelector("#s-save").addEventListener("click", async () => {
      const name = form.querySelector("#s-name").value.trim();
      if (!name) {
        this._toast(this._t("needSetupName"));
        return;
      }
      try {
        const res = await this._ws({
          type: "garden_irrigation/setup/add",
          name,
          mode,
          start_time: time.get(),
          days: days.get(),
        });
        this._addSetupOpen = false;
        if (res && res.entry_id) this._selected = res.entry_id;
        await this._fetch();
      } catch (err) {
        this._toast(this._t("addSetupFail", err.message || err));
      }
    });
    return form;
  }

  /* ---------- dynamic update ---------- */

  _update() {
    const setup = this._currentSetup();
    if (!setup) return;
    for (const zone of setup.zones) {
      const refs = this._refs[zone.zone_id];
      if (!refs) continue;
      const st = this._stateFor(zone);
      const running = !!(st && st.state === "on");
      const attrs = (st && st.attributes) || {};
      const source = attrs.run_source === "scheduled" ? "scheduled" : "manual";

      refs.el.classList.toggle("running", running);

      if (refs.kind === "view") {
        refs.endsAt = running ? attrs.ends_at || null : null;
        refs.pill.hidden = !running;
        if (running) refs.pillText.textContent = this._t(source);
        refs.progress.hidden = !running;
        if (refs.action) {
          refs.action.className = running ? "runbtn stop" : "runbtn";
          refs.action.title = running ? this._t("stop") : this._t("run");
          refs.action.innerHTML = running
            ? `<ha-icon icon="mdi:stop"></ha-icon>`
            : `<ha-icon icon="mdi:play"></ha-icon>`;
        }
        continue;
      }

      // edit mode (configuration only — no run/stop, no countdown, no badge)
      if (this.shadowRoot.activeElement !== refs.slider) {
        refs.slider.value = String(zone.duration);
        refs.durVal.textContent = `${zone.duration} min`;
      }
    }
    this._tick();
  }

  _tick() {
    if (!this._refs) return;
    for (const zoneId of Object.keys(this._refs)) {
      const refs = this._refs[zoneId];
      if (refs.kind !== "view" || !refs.endsAt) continue;
      const left = Math.max(
        0,
        Math.round((new Date(refs.endsAt).getTime() - Date.now()) / 1000)
      );
      const m = Math.floor(left / 60);
      const s = String(left % 60).padStart(2, "0");
      const total = refs.total || 1;
      const pct = Math.min(100, Math.max(0, ((total - left) / total) * 100));
      refs.fill.style.width = `${pct}%`;
      refs.left.textContent = `${m}:${s}`;
    }
  }

  /* ---------- mutations ---------- */

  async _toggleRun(zone) {
    const st = this._stateFor(zone);
    const running = st && st.state === "on";
    if (!zone.entity_id) {
      this._toast(this._t("entityNotReady"));
      return;
    }
    try {
      await this._hass.callService("switch", running ? "turn_off" : "turn_on", {
        entity_id: zone.entity_id,
      });
    } catch (err) {
      this._toast(this._t("actionFailed", err.message || err));
    }
  }

  async _updateSetup(entry_id, changes) {
    try {
      await this._ws({ type: "garden_irrigation/setup/update", entry_id, ...changes });
      await this._fetch();
    } catch (err) {
      this._toast(this._t("updateFail", err.message || err));
    }
  }

  async _deleteSetup(setup) {
    if (!confirm(this._t("confirmDelSetup", setup.name))) return;
    try {
      await this._ws({ type: "garden_irrigation/setup/delete", entry_id: setup.entry_id });
      this._selected = null;
      await this._fetch();
    } catch (err) {
      this._toast(this._t("deleteFail", err.message || err));
    }
  }

  async _updateZone(entry_id, zone_id, changes) {
    try {
      await this._ws({ type: "garden_irrigation/zone/update", entry_id, zone_id, ...changes });
      await this._fetch();
    } catch (err) {
      this._toast(this._t("updateFail", err.message || err));
    }
  }

  async _deleteZone(setup, zone) {
    if (!confirm(this._t("confirmDelZone", zone.name))) return;
    try {
      await this._ws({
        type: "garden_irrigation/zone/delete",
        entry_id: setup.entry_id,
        zone_id: zone.zone_id,
      });
      await this._fetch();
    } catch (err) {
      this._toast(this._t("deleteFail", err.message || err));
    }
  }

  async _addSchedule(entry_id, zone_id, time) {
    try {
      await this._ws({
        type: "garden_irrigation/schedule/add",
        entry_id,
        zone_id,
        time,
        days: WEEKDAYS,
      });
      await this._fetch();
    } catch (err) {
      this._toast(this._t("addSchedFail", err.message || err));
    }
  }

  async _removeSchedule(entry_id, zone_id, index) {
    try {
      await this._ws({
        type: "garden_irrigation/schedule/remove",
        entry_id,
        zone_id,
        index,
      });
      await this._fetch();
    } catch (err) {
      this._toast(this._t("removeSchedFail", err.message || err));
    }
  }

  /* ---------- ui helpers ---------- */

  _make24hTime(value, onChange) {
    const wrap = document.createElement("span");
    wrap.className = "time24";
    const hh = document.createElement("select");
    const mm = document.createElement("select");
    for (let i = 0; i < 24; i++) {
      const o = document.createElement("option");
      o.value = String(i).padStart(2, "0");
      o.textContent = o.value;
      hh.appendChild(o);
    }
    for (let i = 0; i < 60; i++) {
      const o = document.createElement("option");
      o.value = String(i).padStart(2, "0");
      o.textContent = o.value;
      mm.appendChild(o);
    }
    const [h, m] = String(value || "06:00").split(":");
    hh.value = (h || "06").padStart(2, "0");
    mm.value = (m || "00").padStart(2, "0");
    const colon = document.createElement("span");
    colon.className = "colon";
    colon.textContent = ":";
    wrap.append(hh, colon, mm);
    const get = () => `${hh.value}:${mm.value}`;
    if (onChange) {
      hh.addEventListener("change", () => onChange(get()));
      mm.addEventListener("change", () => onChange(get()));
    }
    return { wrap, get };
  }

  _lang() {
    const l =
      (this._hass && (this._hass.locale?.language || this._hass.language)) || "en";
    return String(l).toLowerCase().startsWith("pt") ? "pt" : "en";
  }

  _t(key, ...args) {
    const lang = this._lang();
    const dict = STR[lang] || STR.en;
    const v = dict[key] !== undefined ? dict[key] : STR.en[key];
    return typeof v === "function" ? v(...args) : v;
  }

  _makeDaysEditor(days, editable, onChange) {
    const lang = this._lang();
    const wrap = document.createElement("span");
    wrap.className = "days";
    const sel = new Set(days && days.length ? days : WEEKDAYS);
    WEEKDAYS.forEach((d) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "day" + (sel.has(d) ? " on" : "");
      b.textContent = DAY_SHORT[lang][d];
      b.title = DAY_LABEL[lang][d];
      if (editable) {
        b.addEventListener("click", () => {
          if (sel.has(d)) sel.delete(d);
          else sel.add(d);
          b.classList.toggle("on");
          if (onChange) onChange(WEEKDAYS.filter((x) => sel.has(x)));
        });
      } else {
        b.disabled = true;
      }
      wrap.appendChild(b);
    });
    return { wrap, get: () => WEEKDAYS.filter((x) => sel.has(x)) };
  }

  _switch(checked, onChange) {
    if (customElements.get("ha-switch")) {
      const s = document.createElement("ha-switch");
      s.checked = !!checked;
      s.addEventListener("change", (e) => onChange(e.target.checked));
      return s;
    }
    const s = document.createElement("input");
    s.type = "checkbox";
    s.checked = !!checked;
    s.addEventListener("change", () => onChange(s.checked));
    return s;
  }

  _entityPicker(value, domains, onChange) {
    if (customElements.get("ha-entity-picker")) {
      const p = document.createElement("ha-entity-picker");
      p.hass = this._hass;
      p.includeDomains = domains;
      p.allowCustomEntity = false;
      p.value = value || "";
      p.addEventListener("value-changed", (e) => onChange(e.detail.value));
      return { el: p, get: () => p.value };
    }
    const i = document.createElement("input");
    i.type = "text";
    i.value = value || "";
    i.placeholder = `${domains[0]}.example`;
    i.addEventListener("change", () => onChange(i.value.trim()));
    return { el: i, get: () => i.value.trim() };
  }

  _formatDays(days) {
    if (!days || days.length === 0 || days.length === 7) return this._t("everyDay");
    const lang = this._lang();
    return WEEKDAYS.filter((d) => days.includes(d))
      .map((d) => DAY_LABEL[lang][d].slice(0, 3))
      .join(", ");
  }

  _toast(message) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", {
        detail: { message },
        bubbles: true,
        composed: true,
      })
    );
  }

  _escape(value) {
    return String(value == null ? "" : value).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }
}

customElements.define("garden-irrigation-card", GardenIrrigationCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "garden-irrigation-card",
  name: "Garden Irrigation",
  description: "Set up and control garden irrigation setups, zones and schedules.",
  preview: false,
});

console.info("%c GARDEN-IRRIGATION-CARD ", "color: #03a9f4; font-weight: bold;");
