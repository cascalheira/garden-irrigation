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
const DAY_SHORT = { mon: "M", tue: "T", wed: "W", thu: "T", fri: "F", sat: "S", sun: "S" };
const DAY_LABEL = {
  mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday",
  fri: "Friday", sat: "Saturday", sun: "Sunday",
};

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
  .badge { display: inline-flex; align-items: center; gap: 5px; background: var(--primary-color); color: var(--text-primary-color,#fff); border-radius: 999px; padding: 3px 10px; font-size: .8rem; font-weight: 600; opacity: .92; }
  .badge ha-icon { --mdc-icon-size: 15px; }
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

  /* ---- View mode (compact, read-only) ---- */
  ha-card.view .header { border-bottom: 1px solid var(--divider-color); padding-bottom: 14px; margin-bottom: 2px; }
  .vzone { display: flex; align-items: center; gap: 14px; padding: 16px 6px; }
  .vzone + .vzone { border-top: 1px solid var(--divider-color); }
  .vzone.running { background: rgba(3,169,244,.06); border-radius: 14px; margin: 4px 0; }
  .vzone.running + .vzone { border-top: none; }
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
  .seqbar.view { background: transparent; border-radius: 0; padding: 14px 6px 6px; margin: 0; color: var(--secondary-text-color); }
  .seqbar.view b { color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
`;

class GardenIrrigationCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._setups = [];
    this._fetched = false;
    this._edit = false;
    this._selected = null;
    this._addZoneOpen = false;
    this._addSetupOpen = false;
    this._sig = null;
    this._refs = {};
    this._tick = this._tick.bind(this);
  }

  setConfig(config) {
    this._config = config || {};
    this._edit = config && config.mode === "edit";
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

    clearTimeout(this._retry);
    const cur = this._currentSetup();
    if (cur && cur.zones.some((z) => !z.entity_id)) {
      this._retry = setTimeout(() => this._fetch(), 1000);
    }
  }

  _currentSetup() {
    return this._setups.find((s) => s.entry_id === this._selected) || null;
  }

  /* ---------- render orchestration ---------- */

  _computeSig() {
    return JSON.stringify({
      edit: this._edit,
      selected: this._selected,
      addZone: this._addZoneOpen,
      addSetup: this._addSetupOpen,
      error: this._error,
      setups: this._setups,
    });
  }

  _sync() {
    if (!this._hass) return;
    const sig = this._computeSig();
    if (sig !== this._sig) {
      this._sig = sig;
      this._build();
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

  _build() {
    this._refs = {};
    const root = document.createElement("div");
    const style = document.createElement("style");
    style.textContent = STYLES;
    const card = document.createElement("ha-card");
    card.classList.add(this._edit ? "edit" : "view");

    card.appendChild(this._buildHeader());

    if (this._setups.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = this._edit
        ? "No setups yet. Use “Add setup” to create one (e.g. Garden, Trees)."
        : "No irrigation setups. Switch to edit mode to add one.";
      card.appendChild(empty);
      if (this._addSetupOpen) card.appendChild(this._buildAddSetupForm());
      root.append(style, card);
      this.shadowRoot.replaceChildren(root);
      return;
    }

    if (this._addSetupOpen) card.appendChild(this._buildAddSetupForm());

    const setup = this._currentSetup();
    if (setup) {
      if (this._edit) card.appendChild(this._buildSetupBar(setup));
      if (setup.mode === "sequential") card.appendChild(this._buildSeqBar(setup));
      if (this._addZoneOpen && this._edit)
        card.appendChild(this._buildAddZoneForm(setup));
      if (setup.zones.length === 0 && !this._addZoneOpen) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No zones yet.";
        card.appendChild(empty);
      }
      for (const zone of setup.zones) card.appendChild(this._buildZone(setup, zone));
    }

    root.append(style, card);
    this.shadowRoot.replaceChildren(root);
  }

  _buildHeader() {
    const header = document.createElement("div");
    header.className = "header";

    const icon = document.createElement("ha-icon");
    icon.setAttribute("icon", "mdi:water");
    header.appendChild(icon);

    const setup = this._currentSetup();
    if (this._setups.length <= 1 || !setup) {
      const h1 = document.createElement("h1");
      h1.textContent =
        this._config.title || (setup ? setup.name : "Garden watering");
      header.appendChild(h1);
    } else {
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
      });
      header.appendChild(sel);
    }

    const spacer = document.createElement("div");
    spacer.className = "spacer";
    header.appendChild(spacer);

    if (this._edit) {
      const addZone = document.createElement("button");
      addZone.className = "add-zone";
      addZone.innerHTML = `<ha-icon icon="mdi:plus"></ha-icon> Add zone`;
      addZone.disabled = !setup;
      addZone.addEventListener("click", () => {
        this._addZoneOpen = !this._addZoneOpen;
        this._rebuild();
      });
      header.appendChild(addZone);

      const addSetup = document.createElement("button");
      addSetup.innerHTML = `<ha-icon icon="mdi:folder-plus-outline"></ha-icon> Add setup`;
      addSetup.addEventListener("click", () => {
        this._addSetupOpen = !this._addSetupOpen;
        this._rebuild();
      });
      header.appendChild(addSetup);
    }

    const modeBtn = document.createElement("button");
    modeBtn.innerHTML = this._edit
      ? `<ha-icon icon="mdi:check"></ha-icon> Done`
      : `<ha-icon icon="mdi:pencil"></ha-icon> Edit`;
    if (this._edit) modeBtn.classList.add("active");
    modeBtn.addEventListener("click", () => {
      this._edit = !this._edit;
      this._addZoneOpen = false;
      this._addSetupOpen = false;
      this._rebuild();
    });
    header.appendChild(modeBtn);

    return header;
  }

  _buildSetupBar(setup) {
    const bar = document.createElement("div");
    bar.className = "setup-bar";

    const lbl = document.createElement("span");
    lbl.className = "lbl";
    lbl.textContent = "Scheduling:";
    bar.appendChild(lbl);

    const toggle = document.createElement("div");
    toggle.className = "toggle";
    [
      ["sequential", "Sequential"],
      ["specific", "Specific times"],
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
    del.title = "Delete setup";
    del.innerHTML = `<ha-icon icon="mdi:trash-can-outline"></ha-icon>`;
    del.addEventListener("click", () => this._deleteSetup(setup));
    bar.appendChild(del);

    return bar;
  }

  _buildSeqBar(setup) {
    return this._edit ? this._buildSeqBarEdit(setup) : this._buildSeqBarView(setup);
  }

  _buildSeqBarView(setup) {
    const bar = document.createElement("div");
    bar.className = "seqbar view";

    const txt = document.createElement("span");
    txt.innerHTML = `Starts <b>${this._escape(setup.start_time)}</b> · ${this._escape(
      this._formatDays(setup.days)
    )}`;
    bar.appendChild(txt);

    const spacer = document.createElement("div");
    spacer.style.flex = "1";
    bar.appendChild(spacer);

    const anyRunning = setup.zones.some((z) => {
      const st = this._stateFor(z);
      return st && st.state === "on";
    });
    const run = document.createElement("button");
    if (anyRunning) {
      run.className = "stop";
      run.innerHTML = `<ha-icon icon="mdi:stop"></ha-icon> Stop`;
      run.addEventListener("click", () =>
        this._ws({ type: "garden_irrigation/setup/stop", entry_id: setup.entry_id })
      );
    } else {
      run.innerHTML = `<ha-icon icon="mdi:play"></ha-icon> Run sequence`;
      run.addEventListener("click", () =>
        this._ws({ type: "garden_irrigation/setup/run", entry_id: setup.entry_id })
      );
    }
    bar.appendChild(run);
    return bar;
  }

  _buildSeqBarEdit(setup) {
    const bar = document.createElement("div");
    bar.className = "seq-bar";

    const lbl = document.createElement("span");
    lbl.className = "lbl";
    lbl.textContent = "Starts at";
    bar.appendChild(lbl);

    const time = this._make24hTime(setup.start_time, (v) =>
      this._updateSetup(setup.entry_id, { start_time: v })
    );
    bar.appendChild(time.wrap);

    const on = document.createElement("span");
    on.className = "lbl";
    on.textContent = "on";
    bar.appendChild(on);

    if (this._edit) {
      const days = this._makeDaysEditor(setup.days, true, (d) =>
        this._updateSetup(setup.entry_id, { days: d.length ? d : WEEKDAYS })
      );
      bar.appendChild(days.wrap);
    } else {
      const ds = document.createElement("span");
      ds.className = "days-static";
      ds.textContent = this._formatDays(setup.days);
      bar.appendChild(ds);
    }

    const spacer = document.createElement("div");
    spacer.style.flex = "1";
    bar.appendChild(spacer);

    // Run / stop the whole sequence.
    const anyRunning = setup.zones.some((z) => {
      const st = this._stateFor(z);
      return st && st.state === "on";
    });
    const run = document.createElement("button");
    if (anyRunning) {
      run.className = "stop";
      run.innerHTML = `<ha-icon icon="mdi:stop"></ha-icon> Stop`;
      run.addEventListener("click", () =>
        this._ws({ type: "garden_irrigation/setup/stop", entry_id: setup.entry_id })
      );
    } else {
      run.innerHTML = `<ha-icon icon="mdi:play"></ha-icon> Run sequence`;
      run.addEventListener("click", () =>
        this._ws({ type: "garden_irrigation/setup/run", entry_id: setup.entry_id })
      );
    }
    bar.appendChild(run);

    return bar;
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
      return `${dur} · runs ${this._ordinal(idx + 1)}`;
    }
    const times = (zone.schedules || []).map((s) => this._escape(s.time));
    if (times.length === 0)
      return `${dur} · <span style="opacity:.85">no schedules</span>`;
    const shown = times.slice(0, 3).join(" · ");
    const extra = times.length > 3 ? ` +${times.length - 3}` : "";
    return `${dur} · ${shown}${extra}`;
  }

  _ordinal(n) {
    const s = ["th", "st", "nd", "rd"];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
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

    const actionWrap = document.createElement("div");
    const action = document.createElement("button");
    action.addEventListener("click", () => this._toggleRun(zone));
    actionWrap.appendChild(action);
    el.appendChild(actionWrap);
    refs.action = action;

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
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.hidden = true;
    badge.innerHTML = `<ha-icon icon="mdi:water"></ha-icon><span class="badge-text"></span>`;
    nameRow.appendChild(badge);
    titles.appendChild(nameRow);
    refs.badge = badge;
    refs.badgeText = badge.querySelector(".badge-text");

    // Switch line — shown in edit mode (editable picker), hidden in view.
    if (this._edit) {
      const subWrap = document.createElement("div");
      subWrap.className = "field-row";
      const swField = document.createElement("div");
      swField.className = "field";
      const swLabel = document.createElement("label");
      swLabel.textContent = "Switch / relay";
      const sw = this._entityPicker(
        zone.switch_entity,
        ["switch", "input_boolean"],
        (v) => v && this._updateZone(setup.entry_id, zone.zone_id, { switch_entity: v })
      );
      swField.append(swLabel, sw.el);

      const preField = this._scriptField("Pre-script", zone.pre_script, (v) =>
        this._updateZone(setup.entry_id, zone.zone_id, { pre_script: v || null })
      );
      const postField = this._scriptField("Post-script", zone.post_script, (v) =>
        this._updateZone(setup.entry_id, zone.zone_id, { post_script: v || null })
      );
      subWrap.append(swField, preField, postField);
      titles.appendChild(subWrap);
    }

    head.appendChild(titles);

    if (this._edit) {
      const del = document.createElement("button");
      del.className = "icon-btn";
      del.title = "Delete zone";
      del.innerHTML = `<ha-icon icon="mdi:trash-can-outline"></ha-icon>`;
      del.addEventListener("click", () => this._deleteZone(setup, zone));
      head.appendChild(del);
    }
    el.appendChild(head);

    // Duration slider (always editable)
    const durRow = document.createElement("div");
    durRow.className = "row";
    durRow.innerHTML = `<span class="label">Duration</span>`;
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
      schedLabel.textContent = "Schedules";
      el.appendChild(schedLabel);

      const chips = document.createElement("div");
      chips.className = "chips";
      const schedules = zone.schedules || [];
      if (schedules.length === 0) {
        const none = document.createElement("span");
        none.className = "no-sched";
        none.textContent = "No schedules";
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
      addBtn.textContent = "Add";
      addBtn.addEventListener("click", () =>
        this._addSchedule(setup.entry_id, zone.zone_id, time.get())
      );
      chips.appendChild(addBtn);
      el.appendChild(chips);
    }

    el.appendChild(document.createElement("hr"));

    // Actions
    const actions = document.createElement("div");
    actions.className = "actions";
    const action = document.createElement("button");
    action.addEventListener("click", () => this._toggleRun(zone));
    const status = document.createElement("span");
    status.className = "status";
    actions.append(action, status);
    el.appendChild(actions);
    refs.action = action;
    refs.status = status;
    refs.duration = zone.duration;

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
      <div class="field"><label>Zone name</label><input type="text" id="z-name" placeholder="e.g. Front lawn" /></div>
      <div class="field"><label>Switch / relay</label><div id="z-picker"></div></div>
      <div class="field"><label>Duration (minutes)</label><input type="number" id="z-dur" min="1" max="60" value="10" /></div>
      <div class="form-actions"><button id="z-cancel">Cancel</button><button id="z-save" class="primary">Save zone</button></div>
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
        this._toast("Enter a name and pick a switch.");
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
        this._toast(`Could not add zone: ${err.message || err}`);
      }
    });
    return form;
  }

  _buildAddSetupForm() {
    const form = document.createElement("div");
    form.className = "form";
    form.innerHTML = `
      <div class="field"><label>Setup name</label><input type="text" id="s-name" placeholder="e.g. Trees" /></div>
      <div class="field"><label>Scheduling mode</label>
        <div class="toggle" id="s-mode">
          <button data-v="specific" class="on">Specific times</button>
          <button data-v="sequential">Sequential</button>
        </div>
      </div>
      <div class="field" id="s-seq" hidden>
        <label>Start time &amp; days</label>
        <div class="seq-bar" id="s-seqbar"></div>
      </div>
      <div class="form-actions"><button id="s-cancel">Cancel</button><button id="s-save" class="primary">Create setup</button></div>
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
        this._toast("Enter a setup name.");
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
        this._toast(`Could not add setup: ${err.message || err}`);
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
      refs.endsAt = running ? attrs.ends_at || null : null;

      if (refs.kind === "view") {
        refs.pill.hidden = !running;
        if (running) refs.pillText.textContent = source;
        refs.progress.hidden = !running;
        refs.action.className = running ? "stop" : "";
        refs.action.innerHTML = running
          ? `<ha-icon icon="mdi:stop"></ha-icon> Stop`
          : `<ha-icon icon="mdi:play"></ha-icon> Run`;
        continue;
      }

      // edit mode
      if (running) {
        refs.badge.hidden = false;
        refs.badgeText.textContent = `Watering · ${source}`;
      } else {
        refs.badge.hidden = true;
      }
      if (this.shadowRoot.activeElement !== refs.slider) {
        refs.slider.value = String(zone.duration);
        refs.durVal.textContent = `${zone.duration} min`;
      }
      if (running) {
        refs.action.className = "stop";
        refs.action.innerHTML = `<ha-icon icon="mdi:stop"></ha-icon> Stop`;
      } else {
        refs.action.className = "";
        refs.action.innerHTML = `<ha-icon icon="mdi:play"></ha-icon> Run now`;
        refs.status.innerHTML = `${zone.duration} min manual run`;
      }
    }
    this._tick();
  }

  _tick() {
    if (!this._refs) return;
    for (const zoneId of Object.keys(this._refs)) {
      const refs = this._refs[zoneId];
      if (!refs.endsAt) continue;
      const left = Math.max(
        0,
        Math.round((new Date(refs.endsAt).getTime() - Date.now()) / 1000)
      );
      const m = Math.floor(left / 60);
      const s = String(left % 60).padStart(2, "0");
      if (refs.kind === "view") {
        const total = refs.total || 1;
        const pct = Math.min(100, Math.max(0, ((total - left) / total) * 100));
        refs.fill.style.width = `${pct}%`;
        refs.left.textContent = `${m}:${s}`;
      } else {
        refs.status.innerHTML = `Time left: <b>${m}:${s}</b>`;
      }
    }
  }

  /* ---------- mutations ---------- */

  async _toggleRun(zone) {
    const st = this._stateFor(zone);
    const running = st && st.state === "on";
    if (!zone.entity_id) {
      this._toast("Zone entity not ready yet.");
      return;
    }
    try {
      await this._hass.callService("switch", running ? "turn_off" : "turn_on", {
        entity_id: zone.entity_id,
      });
    } catch (err) {
      this._toast(`Action failed: ${err.message || err}`);
    }
  }

  async _updateSetup(entry_id, changes) {
    try {
      await this._ws({ type: "garden_irrigation/setup/update", entry_id, ...changes });
      await this._fetch();
    } catch (err) {
      this._toast(`Update failed: ${err.message || err}`);
    }
  }

  async _deleteSetup(setup) {
    if (!confirm(`Delete the whole “${setup.name}” setup and its zones?`)) return;
    try {
      await this._ws({ type: "garden_irrigation/setup/delete", entry_id: setup.entry_id });
      this._selected = null;
      await this._fetch();
    } catch (err) {
      this._toast(`Delete failed: ${err.message || err}`);
    }
  }

  async _addSetup() {
    /* handled inline in the form */
  }

  async _updateZone(entry_id, zone_id, changes) {
    try {
      await this._ws({ type: "garden_irrigation/zone/update", entry_id, zone_id, ...changes });
      await this._fetch();
    } catch (err) {
      this._toast(`Update failed: ${err.message || err}`);
    }
  }

  async _deleteZone(setup, zone) {
    if (!confirm(`Delete zone “${zone.name}”?`)) return;
    try {
      await this._ws({
        type: "garden_irrigation/zone/delete",
        entry_id: setup.entry_id,
        zone_id: zone.zone_id,
      });
      await this._fetch();
    } catch (err) {
      this._toast(`Delete failed: ${err.message || err}`);
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
      this._toast(`Could not add schedule: ${err.message || err}`);
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
      this._toast(`Could not remove schedule: ${err.message || err}`);
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

  _makeDaysEditor(days, editable, onChange) {
    const wrap = document.createElement("span");
    wrap.className = "days";
    const sel = new Set(days && days.length ? days : WEEKDAYS);
    WEEKDAYS.forEach((d) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "day" + (sel.has(d) ? " on" : "");
      b.textContent = DAY_SHORT[d];
      b.title = DAY_LABEL[d];
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
    if (!days || days.length === 0 || days.length === 7) return "every day";
    return WEEKDAYS.filter((d) => days.includes(d))
      .map((d) => DAY_LABEL[d].slice(0, 3))
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
